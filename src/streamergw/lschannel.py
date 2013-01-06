from twisted.web import server
from twisted.internet import interfaces, defer
from zope.interface import implements

from MCSPBuffers import MCSPBuffer, MCSPConsumer
from utils import returnHTTPError


class LSConsumer(MCSPConsumer):
    
    implements(interfaces.IProducer)
    
    def __init__(self, lschannel, consumer):
        super(LSConsumer, self).__init__()
        
        self.lschannel = lschannel
        self.consumer = consumer
        self.buffer = None
        self.defer = None
    
    def beginTransfer(self, thebuffer):
        self.buffer = thebuffer
        
        self._send_data = True
        self.buffer.addConsumer(self)
        self.consumer.registerProducer(self, False)
        
        self.defer = defer.Deferred()
        return self.defer
    
    #Interface methods
    def resumeProducing(self):
        if self.buffer.length - self.position > 0:
            data = self.buffer.read(self)
            self.consumer.write(data)
            
            self.lschannel._consumerSentData()
    
    def pauseProducing(self):
        pass
    
    def stopProducing(self):
        if self.consumer.producer:
            self.consumer.unregisterProducer()
        if not self.consumer.finished:
            self.consumer.finish()
        if self.buffer:
            self.buffer.removeConsumer(self)
        if self.defer:
            self.defer.callback(self)


class LSChannel(object):
    """A livestreamer channel.
    """
    
    LS_MAX_BUFFER_SIZE = 16384*4
    
    def __init__(self, server, channel, url):
        self._server = server
        
        self._channel = channel
        self._url = url
        self._streams = None
        self._stream = None
        self._streamQuality = None
        self._fd = None
        
        self._consumers = []
        self._buffer = None
        
        self._reset = False
    
    def geturl(self):
        return self._url
    url = property(geturl)
    
    def getstreamquality(self):
        return self._streamQuality
    streamQuality = property(getstreamquality)
    
    def hasQuality(self, quality):
        if not self._streams:
            self._streams = self._channel.get_streams()
        return quality in self._streams
    
    def getChannelQualities(self):
        if not self._streams:
            self._streams = self._channel.get_streams()
        return self._streams.keys()
    
    def isPlaying(self):
        return not self._streamQuality is None
    
    def streamRequest(self, request, quality, forcequality = False):
        try:
            if not self.hasQuality(quality): #hasQuality() sets self._streams in case they are not there already, self._streams should be set up manually if this is removed
                return returnHTTPError(request, 404, "<html><body>Error stream quality %s not found</body></html>" % quality,
                                       debugprint="Bad quality param %s" %quality)
        except Exception as e:
            return returnHTTPError(request, 500, "<html><body>Error accesing the channel</body></html>",
                                   debugprint="Error accessing the channel %s" %str(e))
        
        #if not self._streams:
            #try:
                #self._streams = self._channel.get_streams()
            #except Exception as e:
                #returnHTTPError(request, 404, "<html><body>Error retrieving the list of streams for this channel</body></html>",
                #                debugprint="Error getting stream list, %s" %str(e))
        
        if forcequality and self._streamQuality and self._streamQuality != quality:
            if self._fd:
                if hasattr(self._fd, "close"):
                    self._fd.close()
                self._fd = None
            self._stream = None
            self._streamQuality = None
        
        if not self._stream:
            try:
                self._beginStream(quality)
            except Exception as e:
                self._reset_channel()
                self._server.removeChannel(self)
                return returnHTTPError(request, 404, "<html><body>%s</body></html>" %str(e),
                                       debugprint="Error creating fd: %s" %str(e))
        
        lsconsumer = LSConsumer(self, request)
        self._consumers.append(lsconsumer)
        
        request.setResponseCode(200)
        request.responseHeaders.setRawHeaders("content-type", ["video/raw"])
        
        self._consumerSentData() #initial read
        
        d = lsconsumer.beginTransfer(self._buffer)
        d.addCallback(self._CBremoveConsumer)
        
        return server.NOT_DONE_YET
    
    def changeStream(self, request, quality):
        return self.streamRequest(request, quality, forcequality = True)
    
    def _beginStream(self, quality):
        self._streamQuality = quality
        self._stream = self._streams[quality]
        self._fd = self._stream.open()
        self._buffer = MCSPBuffer()
    
    def _consumerSentData(self):
        if self._buffer.length < self.LS_MAX_BUFFER_SIZE:
            chunk = ''
            try:
                chunk = self._fd.read(1024)
            except Exception as e:
                print 'DEBUG: Read failed, finishing, %s' %str(e)
                self._reset_channel()
                self._server.removeChannel(self)
                return
            if not chunk:
                print 'DEBUG: chunk empty, finishing'
                self._reset_channel()
                self._server.removeChannel(self)
                return
            
            self._buffer.write(chunk)
    
    def _CBremoveConsumer(self, lsconsumer):
        try:
            self._consumers.remove(lsconsumer)
        except ValueError:
            return
        
        if not self._reset and len(self._consumers) <= 0:
            self._reset_channel()
            self._server.removeChannel(self)
    
    def _reset_channel(self):
        print '_reset_channel start'
        self._reset = True
        
        for lsconsumers in self._consumers:
            lsconsumers.stopProducing()
        
        # All streams are not guaranteed to support .close()
        if self._fd:
            if hasattr(self._fd, "close"):
                self._fd.close()
            self._fd = None
        self._stream = None
        self._streamQuality = None
        self._buffer = None
        
        self._reset = False
        print '_reset_channel end'

