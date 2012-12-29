from twisted.internet import reactor, defer, interfaces
from twisted.internet.protocol import Protocol
from twisted.web import server
from zope.interface import implements
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

import subprocess
from random import randint
from os import kill

from MCSPBuffers import MCSPBuffer, MCSPConsumer


class SopcastConsumer(MCSPConsumer):
    
    implements(interfaces.IProducer)
    
    def __init__(self, sopchannel, consumer):
        super(SopcastConsumer, self).__init__()
        
        self.sopchannel = sopchannel
        self.buffer = None
        self.consumer = consumer
    
    def beginTransfer(self, thebuffer):
        self.buffer = thebuffer
        
        self._send_data = True #does resumeProducing get called the first time, or is it assumed?
        self.buffer.addConsumer(self)
        self.consumer.registerProducer(self, False)
    
    def sendData(self): #TODO if self._send_data and position == self.buffer.length dont add to buffer, just send it directly
        print 'SoapConsumer.sendData start, %s' %str(self.buffer.length)
        old_length = self.buffer.length
        data = self.buffer.read(self)
        self.consumer.write(data)
        print 'SoapConsumer.sendData 2, %s' %str(self.buffer.length)
        if old_length - self.position > 0:
            print 'SoapConsumer.sendData 3'
            self.sopchannel._consumerSentData()
        print 'SoapConsumer.sendData 4'
    
    #Interface methods
    def resumeProducing(self):
        self.sendData()
    
    def pauseProducing(self):
        pass
    
    def stopProducing(self):
        if self.buffer:
            self.buffer.removeConsumer(self)
        self.sopchannel._removeConsumer(self)
    
    #Callback
    def CBGone(self, ignore):
        self.stopProducing()


class SopcastChannel(Protocol):
    """A sopcast channel.
    """
    SOPCAST_INITIAL_TIMEOUT = 3
    SOPCAST_ELIMINATION_TIMEOUT = 20
    
    SOPCAST_MAX_BUFFER_SIZE = 16384*4
    
    def __init__(self, server, path, url):
        self._server = server
        self._path = path
        
        self._url = url
        self._sp_sc_url = None
        self._pid = None
        
        self._buffer = None
        self._protocol_connected = False
        self._transport_paused = False
        
        self._sopconsumers = []
        
        self._calllater = None
        
        self._reset = False
        
        self._elimination_timer = None
    
    #Protocol methods
    def dataReceived(self, bytes):
        print 'SopcastChannel.dataReceived start, %s' %str(self._buffer.length)
        self._buffer.write(bytes)
        print 'SopcastChannel.dataReceived 1, %s' %str(self._buffer.length)
        #notifying consumers the new data
        for sopconsumer in self._sopconsumers:
            sopconsumer.sendData()
        
        #checking if we have space in the buffer for more data
        if self._buffer.length > self.SOPCAST_MAX_BUFFER_SIZE:
            print 'SopcastChannel.dataReceived paused, %s' %str(self._buffer.length)
            self.transport.pauseProducing()
            self._transport_paused = True
        print 'SopcastChannel.dataReceived end, %s' %str(self._buffer.length)
    
    def connectionLost(self, reason):
        print 'DEBUG: Connection with sp-sc has closed, closing channel. Reason: %s' %reason.getErrorMessage()
        if not self._protocol_connected:
            return
        self._protocol_connected = False
        
        #check error and maybe try again?
        
        self._resetChannel()
        self._server.removeChannel(self)
    
    #DEBUG
    def connectionMade(self):
        #print 'Protocol made connection'
        pass
    
    #Agent callbacks
    def cbAgentSuccess(self, response):
        print 'DEBUG: Connection with sp-sc succesful, setting Protocol.'
        self._buffer = MCSPBuffer()
        
        #starting consumers
        for sopconsumer in self._sopconsumers:
            sopconsumer.consumer.setResponseCode(200)
            sopconsumer.consumer.responseHeaders.setRawHeaders("content-type", ["video/raw"])
            sopconsumer.beginTransfer(self._buffer)
        
        response.deliverBody(self)
        self.transport.resumeProducing()
        self._protocol_connected = True
    
    def cbAgentError(self, failure):
        #try again?
        print 'DEBUG: Error connecting with sp-sc port, closing channel'
        
        for sopconsumer in self._sopconsumers:
            sopconsumer.consumer.setResponseCode(500)
            sopconsumer.consumer.write("<html><body>Error, could not connect to sp-sc url</body></html>")
            #finalized in self._resetChannel()
        self._resetChannel()
        self._server.removeChannel(self)
    
    #Rest of methods
    def streamRequest(self, request):
        if not self._pid:
            try:
                self._beginStream()
            except Exception as e:
                print "Closing channel. Error starting the stream: " + str(e)
                self._resetChannel()
                self._server.removeChannel(self)
                request.setResponseCode(404)
                return "<html><body>%s</body></html>" % e
            
            #give sp-sc SOPCAST_INITIAL_TIMEOUT seconds to do its thing
            self._calllater = reactor.callLater (self.SOPCAST_INITIAL_TIMEOUT, self._initialCheckAlive)
        
        sopconsumer = SopcastConsumer(self, request)
        self._sopconsumers.append(sopconsumer)
        request.notifyFinish().addBoth(sopconsumer.CBGone)
        if self._protocol_connected:
            sopconsumer.consumer.setResponseCode(200)
            sopconsumer.consumer.responseHeaders.setRawHeaders("content-type", ["video/raw"])
            sopconsumer.beginTransfer(self._buffer)
        
        if self._elimination_timer:
            print 'New client, elimination timer removed %s' %str(self._buffer.length)
            self._elimination_timer.cancel()
            self._elimination_timer = None
        
        return server.NOT_DONE_YET
    
    def _beginStream(self):
        if self._pid:
            return
        
        inport = randint(10025, 65535)
        outport = randint(10025, 65535)
        while inport == outport:
            outport = randint(10025, 65535)
        
        self._pid = subprocess.Popen([self._path, self._url, str(inport), str(outport)], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self._sp_sc_url = 'http://localhost:' + str(outport) + '/tv.asf'
    
    def _endStream(self):
        if not self._pid:
            return
        kill(self._pid.pid, 9)
        self._pid = None
    
    def _initialCheckAlive(self):
        self._calllater = None
        
        if(self._pid.poll()): #sp-sc is not running
            self._pid = None
            #TODO check the output of the sp-sc subprocess to check what happened, if it was the ports relaunch
            
            for sopconsumer in self._sopconsumers:
                sopconsumer.consumer.setResponseCode(500)
                sopconsumer.consumer.write("<html><body>Error, could not start sopcast channel</body></html>")
                #finalized in self._resetChannel()
            self._resetChannel()
            self._server.removeChannel(self)
        
        else: #its running fine, connecting to the sp-sc socket
            #TODO monitor the output of the subprocess sp-sc, nblockAvailable will show the % of the sp-sc buffer, find how to get other info
            
            agent = Agent(reactor)
            d = agent.request('GET',
                              self._sp_sc_url,
                              Headers({'User-Agent': ['streamergw client']}),
                              None)
            d.addCallback(self.cbAgentSuccess)
            d.addErrback(self.cbAgentError)
    
    def _setEliminationTimer(self):
        if self._elimination_timer: #should never happen
            return
        
        self._elimination_timer = reactor.callLater (self.SOPCAST_ELIMINATION_TIMEOUT, self._eliminationCB)
    
    def _eliminationCB(self):
        self._elimination_timer = None
        
        self._resetChannel()
        self._server.removeChannel(self)
    
    def _resetChannel(self):
        self._reset = True
        print 'DEBUG: _resetChannel start'
        if self._calllater:
            self._calllater.cancel()
            self._calllater = None
        
        if self._elimination_timer:
            self._elimination_timer.cancel()
            self._elimination_timer = None
        
        if self._protocol_connected:
            self._protocol_connected = False
            self.transport.stopProducing()
        self._transport_paused = False
        
        for sopconsumer in self._sopconsumers:
            if sopconsumer.consumer.producer:
                sopconsumer.consumer.unregisterProducer()
            if not sopconsumer.consumer.finished:
                sopconsumer.consumer.finish()
        #self._sopconsumers = []
        
        self._buffer = None
        
        self._endStream()
        self._sp_sc_url = None
        print 'DEBUG: _resetChannel end'
        self._reset = False
    
    #Consumer methods
    def _consumerSentData(self):
        print 'SoapChannel._consumerSentData start'
        if self._transport_paused is True and self._buffer.length < self.SOPCAST_MAX_BUFFER_SIZE:
            print 'SoapChannel._consumerSentData resumed, %s' %str(self._buffer.length)
            self._transport_paused = False
            self.transport.resumeProducing()
    
    def _removeConsumer(self, sopconsumer):
        try:
            self._sopconsumers.remove(sopconsumer)
        except ValueError:
            return
        
        #if it was the last consumer close the channel
        if len(self._sopconsumers) <= 0 and not self._reset:
            self._setEliminationTimer()
    
    def geturl(self):
        return self._url
    url = property(geturl)

