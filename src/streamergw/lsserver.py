from twisted.web import resource

from livestreamer import Livestreamer

from lschannel import LSChannel
from utils import returnHTTPError


class NoURL(Exception):
    pass

class NoUserName(Exception):
    pass

class NoPassword(Exception):
    pass

class QualityNotFound(Exception):
    pass

class LSHttpServer(resource.Resource):
    isLeaf = True
    
    livestreamer = Livestreamer()
    channels = {}
    
    def render_GET(self, request):
        request.responseHeaders.setRawHeaders("server", ["Livestreamer HTTP Server"])
        
        info = request.args and "info" in request.args and request.args["info"][0]
        if info:
            return self._handleInfoRequest(request, info)
        
        quality = request.args and "stream" in request.args and request.args["stream"][0]
        if not quality:
            quality = "best"
        
        try:
            url = self._handleURL(request.args)
        except NoURL:
            return returnHTTPError(request, 500, "<html><body>Error Missing URL parameter</body></html>",
                                   debugprint="Wrong URL")
        except (NoUserName, NoPassword):
            return returnHTTPError(request, 500, "<html><body>Error Missing login parameter</body></html>",
                                   debugprint="Wrong login parameters")
        
        print "Q:", quality
        print "U:", url
        
        try:
            channel = self._getChannel(url, checkquality=quality, add=True)
        except QualityNotFound:
            return returnHTTPError(request, 500, "<html><body>Channel has no stream with quality %s</body></html>" %quality,
                                   debugprint='Quality not found')
        except Exception as e:
            return returnHTTPError(request, 500, "<html><body>Error accesing the channel</body></html>",
                                   debugprint='Was not able to access the channel stream: %s' %str(e))
        
        change = request.args and "change" in request.args and request.args["change"][0]
        if change:
            return channel.streamStream(request, quality, forcequality = True)
        
        return channel.streamRequest(request, quality)
    
    def _handleURL(self, requestargs):
        url = requestargs and "url" in requestargs and requestargs["url"][0]
        if not url:
             raise NoURL()
        url = url.lower()
        
        username = requestargs and "username" in requestargs and requestargs["username"][0]
        password = requestargs and "password" in requestargs and requestargs["password"][0]
        
        #removing the specific server from twitch.tv url
        if 'twitch.tv' in url:
            url = 'http://twitch.tv' + url.split('twitch.tv', 1)[1]
        
        #Login info is mandatory for gomtv
        if 'gomtv.net' in url:
            if not username:
                raise NoUserName()
            if not password:
                raise NoPassword()
            
            self.livestreamer.set_plugin_option("gomtv", "username", username)
            self.livestreamer.set_plugin_option("gomtv", "password", password)
        
        return url
    
    def _getChannel(self, url, checkquality=None, add=False):
        channel = None
        needadd = False
        
        try:
            channel = self.channels[url]
        except KeyError:
            try:
                channel = LSChannel(self, self.livestreamer.resolve_url(url), url)
            except Exception as e:
                raise e
            
            needadd = True
        
        if checkquality:
            try:
                quality = channel.hasQuality(checkquality)
            except Exception as e:
                raise e
            if not quality:
                raise QualityNotFound()
        
        if add and needadd:
            self.channels[url] = channel
        
        return channel
    
    def _handleInfoRequest(self, request, info):
        print info
        if info == "qualitylist":
            try:
                url = self._handleURL(request.args)
            except NoURL:
                print 'NoURL'
                return returnHTTPError(request, 500, "<html><body>Error Missing URL parameter</body></html>")
            except (NoUserName, NoPassword):
                print 'NoLog'
                return returnHTTPError(request, 500, "<html><body>Error Missing login parameter</body></html>")
            
            try:
                channel = self._getChannel(url)
            except Exception as e:
                print 'Something channel'
                return returnHTTPError(request, 500, "<html><body>Could not find a channel with that url %s</body></html>" %url)
            
            try:
                qualities = channel.getChannelQualities()
            except Exception as e:
                print 'something qualities'
                return returnHTTPError(request, 500, "<html><body>Error accessing the streams of the channel</body></html>" %url)
            
            request.setResponseCode(200)
            request.responseHeaders.setRawHeaders("content-type", ["text/plain"])
            return "<html><body>%s</body></html>" %','.join(qualities)
        
        if info == 'playingquality':
            try:
                url = self._handleURL(request.args)
            except NoURL:
                return returnHTTPError(request, 500, "<html><body>Error Missing URL parameter</body></html>")
            except (NoUserName, NoPassword):
                return returnHTTPError(request, 500, "<html><body>Error Missing login parameter</body></html>")
            
            try:
                channel = channels[url]
            except KeyError:
                return returnHTTPError(request, 500, "<html><body>Channel is not connected</body></html>")
            
            if not channel.streamQuality:
                return returnHTTPError(request, 500, "<html><body>Channel is not connected</body></html>")
            
            request.setResponseCode(200)
            request.responseHeaders.setRawHeaders("content-type", ["text/plain"])
            return "<html><body>%s</body></html>" %channel.streamQuality
        
        else:
            return returnHTTPError(request, 500, "<html><body>Unknown info command %s</body></html>" %info)
    
    def removeChannel(self, channel):
        try:
            del self.channels[channel.url]
            print "Livestreamer Channel removed"
        except ValueError:
            print 'channelClosing did not find the channel'

