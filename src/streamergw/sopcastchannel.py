from twisted.internet import reactor
from twisted.web import server

import subprocess, threading
from random import randint
from os import kill

from utils import getLocalIP


class SopcastChannel(object):
    """A sopcast channel.
    """
    
    SOPCAST_INITIAL_TIMEOUT = 3
    SOPCAST_ELIMINATION_TIMEOUT = 20
    
    def __init__(self, server, path, url):
        self._server = server
        self._path = path
        
        self._url = url
        self._sp_sc_url = None
        self._pid = None
        self._pidlock = threading.Lock()
        
        self._requests = []
        self.reference = 0
        
        self._calllater = None
        self._elimination_timer = None
        
        self._reset = False
    
    def geturl(self):
        return self._url
    url = property(geturl)
    
    def streamRequest(self, request):
        if not self._pid:
            try:
                self._beginStream(request.getClientIP())
            except Exception as e:
                print "Closing channel. Error starting the stream: " + str(e)
                self._resetChannel()
                self._server.removeChannel(self)
                request.setResponseCode(404)
                return "<html><body>%s</body></html>" % e
            
            #give sp-sc SOPCAST_INITIAL_TIMEOUT seconds to do its thing
            self._calllater = reactor.callLater (self.SOPCAST_INITIAL_TIMEOUT, self._initialCheckAlive)
        
        if self._elimination_timer:
            print 'New client, elimination timer removed'
            self._elimination_timer.cancel()
            self._elimination_timer = None
        
        if self._calllater:
            self._requests.append(request)
            request.notifyFinish().addBoth(self._requestGoneCB, request)
            return server.NOT_DONE_YET
        
        self.reference += 1
        request.setResponseCode(200)
        request.responseHeaders.setRawHeaders("content-type", ["text/plain"])
        return "<html><body>%s</body></html>" %self._sp_sc_url
    
    def removeRequest(self, request):
        if self._calllater:
            request.setResponseCode(500)
            return "<html><body>Initial period going on, wait.</body></html>" % e
        
        self.reference -= 1
        
        if self.reference <= 0:
            self._setEliminationTimer()
            request.setResponseCode(200)
            return "<html><body>Closing channel</body></html>"
        else:
            request.setResponseCode(200)
            return "<html><body>Reference removed. Channel will remain open for someone else</body></html>"
    
    def _beginStream(self, clientIP):
        if self._pid:
            return
        
        inport = randint(10025, 65535)
        outport = randint(10025, 65535)
        while inport == outport:
            outport = randint(10025, 65535)
        
        self._pid = subprocess.Popen([self._path, self._url, str(inport), str(outport)], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        
        localIP = getLocalIP(clientIP)
        self._sp_sc_url = 'http://' + localIP + ':' + str(outport) + '/tv.asf'
    
    def _readSoapConnection(self):
        while(1):
            self._pidlock.acquire()
            if self._pid is None:
                self._pidlock.release()
                return
            line = self._pid.stdout.readline()
            self._pidlock.release()
            
            if 'nblockAvailable' in line:
                col = line.split()
                try:
                    pr = col[2].split('=')
                    try:
                        percent = int(pr[1])
                    except:
                        percent = 0
                    if percent > 100:
                        percent = -1
                    reactor.callFromThread(self._reportStatus, percent)
                except:
                    pass
    
    def _reportStatus(self, status):
        print 'Sopcast buffer status: %d' %status
    
    def _endStream(self):
        self._pidlock.acquire()
        if not self._pid:
            self._pidlock.release()
            return
        kill(self._pid.pid, 9)
        self._pid = None
        self._pidlock.release()
        
        self._sp_sc_url = None
    
    def _requestGoneCB(self, ignore, request):
        try:
            self._requests.remove(request)
        except ValueError:
            pass
    
    def _initialCheckAlive(self):
        self._calllater = None
        
        if(self._pid.poll()): #sp-sc is not running
            self._pid = None
            #TODO check the output of the sp-sc subprocess to check what happened, if it was the ports relaunch
            
            self._resetChannel()
            self._server.removeChannel(self)
        
        else: #its running fine, connecting to the sp-sc socket
            reactor.callInThread(self._readSoapConnection)
            
            for request in self._requests:
                self.reference += 1
                request.setResponseCode(200)
                request.responseHeaders.setRawHeaders("content-type", ["text/plain"])
                request.write("<html><body>%s</body></html>" %self._sp_sc_url)
                request.finish()
            self._requests = []
            
    
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
        
        for request in self._requests:
            request.setResponseCode(402)
            request.write("<html><body>The connection has been closed</body></html>")
            request.finish()
        self._requests = []
        self.reference = 0
        
        self._endStream()
        
        print 'DEBUG: _resetChannel end'
        self._reset = False

