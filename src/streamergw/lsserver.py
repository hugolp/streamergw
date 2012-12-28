from twisted.web import resource

from livestreamer import Livestreamer

from lschannel import LSChannel


class LSHttpServer(resource.Resource):
    isLeaf = True
    
    livestreamer = Livestreamer()
    channels = {}
    
    def render_GET(self, request):
        request.responseHeaders.setRawHeaders("server", ["Livestreamer HTTP Server"])
        
        info = request.args and "info" in request.args and request.args["info"][0]
        if info:
            return self.handleInfoRequest(request, info)
        
        quality = request.args and "stream" in request.args and request.args["stream"][0]
        if not quality:
            quality = "best"
        
        url = self._handleURL(request.args)
        if not url:
             request.setResponseCode(500)
             return "<html><body>Error Missing URL parameter</body></html>"
        
        print "Q:", quality
        print "U:", url
        
        add = False
        try:
            channel = self.channels[url]
        except KeyError:
            try:
                channel = LSChannel(self, self.livestreamer.resolve_url(url), url)
            except Exception as e:
                print str(e)
                request.setResponseCode(500)
                return "<html><body>Could not find a channel with that url %s</body></html>" %url
            
            add = True
        
        try:
            if not channel.hasQuality(quality):
                request.setResponseCode(500)
                return "<html><body>Channel has no stream with quality %s</body></html>" %quality
        except Exception as e:
            print e
            request.setResponseCode(500)
            return "<html><body>Error accesing the channel</body></html>"
        
        if add:
            self.channels[url] = channel
        
        change = request.args and "change" in request.args and request.args["change"][0]
        if change is 'True':
            return channel.streamStream(request, quality, forcequality = True)
        
        return channel.streamRequest(request, quality)
    
    def _handleURL(self, requestargs):
        url = requestargs and "url" in requestargs and requestargs["url"][0]
        if not url:
             return None
        url = url.lower()
        
        #removing the specific server from twitch.tv url
        if 'twitch.tv' in url:
            url = 'http://twitch.tv' + url.split('twitch.tv', 1)[1]
        
        return url
    
    def _getChannel(self, url):
        channel = None
        try:
            channel = self.channels[url]
        except KeyError:
            try:
                channel = LSChannel(self, self.livestreamer.resolve_url(url))
            except e:
                raise e
                return
        
        return channel
    
    def _handleInfoRequest(self, request, info):
        if info is "qualitylist":
            url = self._handleURL(request.args)
            if not url:
                request.setResponseCode(500)
                return "<html><body>Error Missing URL parameter</body></html>"
            
            try:
                channel = self._getChannel(url)
            except Exception as e:
                print e
                request.setResponseCode(500)
                return "<html><body>Could not find a channel with that url %s</body></html>" %url
            
            try:
                qualities = channel.getChannelQualities()
            except Exception as e:
                print e
                request.setResponseCode(500)
                return "<html><body>Error accessing the streams of the channel</body></html>"
            
            request.setResponseCode(200)
            request.responseHeaders.setRawHeaders("content-type", ["text/plain"])
            return "<html><body>%s</body></html>" %','.join(qualities)
        
        if info is 'playingquality':
            url = self._handleURL(request.args)
            if not url:
                request.setResponseCode(500)
                return "<html><body>Error Missing URL parameter</body></html>"
            
            try:
                channel = channels[url]
            except KeyError:
                request.setResponseCode(500)
                return "<html><body>Channel is not connected</body></html>"
            
            if not channel.streamQuality:
                request.setResponseCode(500)
                return "<html><body>Channel is not connected</body></html>"
            
            request.setResponseCode(200)
            request.responseHeaders.setRawHeaders("content-type", ["text/plain"])
            return "<html><body>%s</body></html>" %channel.streamQuality
        
        else:
            request.setResponseCode(500)
            return "<html><body>Unknown info command %s</body></html>" %info
    
    def removeChannel(self, channel):
        try:
            del self.channels[channel.url]
            print "Livestreamer Channel removed"
        except ValueError:
            print 'channelClosing did not find the channel'

