from twisted.web import resource

from distutils.spawn import find_executable

from sopcastchannel import SopcastChannel


class SopcastHttpServer(resource.Resource):
    isLeaf = True
    
    channels = {}
    
    def __init__(self, path):
        self._path = path
        resource.Resource.__init__(self)
    
    @staticmethod
    def getPath():
        return find_executable('sp-sc')
    
    def render_GET(self, request):
        request.responseHeaders.setRawHeaders("server", ["Sopcast HTTP Server"])
        
        stop = request.args and "stop" in request.args and request.args["stop"][0]
        if stop:
            try:
                channel = self.channels[stop]
            except KeyError:
                request.setResponseCode(500)
                return "<html><body>Error, channel to stop not found</body></html>"
            
            return channel.removeRequest(request)
        
        url = request.args and "url" in request.args and request.args["url"][0]
        if not url:
            request.setResponseCode(500)
            return "<html><body>Error Missing Url parameter</body></html>"
        
        if not url.startswith('sop://'):
            request.setResponseCode(500)
            return "<html><body>Error, Url parameter is not valid</body></html>"
        
        try:
            channel = self.channels[url]
        except KeyError:
            channel = SopcastChannel(self, self._path, url)
            self.channels[url] = channel
        
        return channel.streamRequest(request)
    
    def removeChannel(self, channel):
        try:
            print 'DEBUG: Sopcast, removing channel %s' %channel.url
            del self.channels[channel.url]
        except KeyError:
            print 'channelClosing did not find the channel'

