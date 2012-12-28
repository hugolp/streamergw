from twisted.web import server, resource
from twisted.internet import reactor

from lsserver import LSHttpServer
from sopcastserver import SopcastHttpServer


def main():
    root = resource.Resource()
    root.putChild('livestreamer', LSHttpServer())
    
    #checking if "sp-sc-auth" is present
    sopcastpath = SopcastHttpServer.getPath()
    if sopcastpath:
        root.putChild('sopcast', SopcastHttpServer(sopcastpath))

    site = server.Site(root)
    reactor.listenTCP(8080, site)
    reactor.run()

if __name__ == '__main__':
    main()

