'''
Created on Sep 3, 2013

@author: pvicente
'''
from twisted.words.xish.domish import Element, ParserError
from lxml import etree
from io import BytesIO
from _regex_core import ParseError

class ExpatElementStream:
    def __init__(self):
        import pyexpat
        self.DocumentStartEvent = None
        self.ElementEvent = None
        self.DocumentEndEvent = None
        self.error = pyexpat.error
        self.parser = pyexpat.ParserCreate("UTF-8", " ")
        self.parser.StartElementHandler = self._onStartElement
        self.parser.EndElementHandler = self._onEndElement
        self.parser.CharacterDataHandler = self._onCdata
        self.parser.StartNamespaceDeclHandler = self._onStartNamespace
        self.parser.EndNamespaceDeclHandler = self._onEndNamespace
        self.currElem = None
        self.defaultNsStack = ['']
        self.documentStarted = 0
        self.localPrefixes = {}

    def parse(self, buffer):
        try:
            print '"%s"'%(buffer)
            self.parser.Parse(buffer)
        except self.error, e:
            raise ParserError, str(e)

    def _onStartElement(self, name, attrs):
        print '_onStartElement', name, attrs
        # Generate a qname tuple from the provided name.  See
        # http://docs.python.org/library/pyexpat.html#xml.parsers.expat.ParserCreate
        # for an explanation of the formatting of name.
        qname = name.rsplit(" ", 1)
        if len(qname) == 1:
            qname = ('', name)

        # Process attributes
        for k, v in attrs.items():
            if " " in k:
                aqname = k.rsplit(" ", 1)
                attrs[(aqname[0], aqname[1])] = v
                del attrs[k]

        # Construct the new element
        e = Element(qname, self.defaultNsStack[-1], attrs, self.localPrefixes)
        self.localPrefixes = {}

        # Document already started
        if self.documentStarted == 1:
            if self.currElem != None:
                self.currElem.children.append(e)
                e.parent = self.currElem
            self.currElem = e

        # New document
        else:
            self.documentStarted = 1
            self.DocumentStartEvent(e)

    def _onEndElement(self, tag):
        print '_onEndElement', tag
        # Check for null current elem; end of doc
        if self.currElem is None:
            self.DocumentEndEvent()

        # Check for parent that is None; that's
        # the top of the stack
        elif self.currElem.parent is None:
            self.ElementEvent(self.currElem)
            self.currElem = None

        # Anything else is just some element in the current
        # packet wrapping up
        else:
            self.currElem = self.currElem.parent

    def _onCdata(self, data):
        print '_onCdata', data
        if self.currElem != None:
            self.currElem.addContent(data)

    def _onStartNamespace(self, prefix, uri):
        print '_onStartNamespace', prefix, uri
        # If this is the default namespace, put
        # it on the stack
        if prefix is None:
            self.defaultNsStack.append(uri)
        else:
            self.localPrefixes[prefix] = uri

    def _onEndNamespace(self, prefix):
        print '_onEndNamespace', prefix
        # Remove last element on the stack
        if prefix is None:
            self.defaultNsStack.pop()


class LXMLFeedParserStream:
    def __init__(self):
        self.DocumentStartEvent = None
        self.ElementEvent = None
        self.DocumentEndEvent = None
        self.parser = etree.XMLParser(resolve_entities=False, ns_clean=False, remove_blank_text=True, target=self, strip_cdata=True)
        self.currElem = None
        self.defaultNsStack = ['']
        self.NsDict=dict()
        self.documentStarted = 0
        self.localPrefixes = {}
    
    def parse(self, data):
        try:
            self.parser.feed(data)
        except Exception as e:
            raise ParseError, str(e)
    
    def start(self, tag, attrib, ns):
        print 'start', tag, attrib, ns
        
        ##Add namespaces
        for prefix, uri in ns.iteritems():
            if prefix is None:
                self.defaultNsStack.append(uri)
                self.NsDict[tag]=True
            else:
                self.localPrefixes[prefix] = uri
        
        tag = etree.QName(tag)
        qname = ('', tag.localname) if tag.namespace is None else (tag.namespace, tag.localname)
        
        #=======================================================================
        # for k, v in attrs.items():
        #     if " " in k:
        #         aqname = k.rsplit(" ", 1)
        #         attrs[(aqname[0], aqname[1])] = v
        #         del attrs[k]
        #=======================================================================

        # Construct the new element
        e = Element(qname, self.defaultNsStack[-1], attrib, self.localPrefixes)
        
        self.localPrefixes = {}
        
        # Document already started
        if self.documentStarted == 1:
            if self.currElem != None:
                self.currElem.children.append(e)
                e.parent = self.currElem
            self.currElem = e
        
        # New document
        else:
            self.documentStarted = 1
            self.DocumentStartEvent(e)
    
    def end(self, tag):
        print 'end', tag
        
        if self.NsDict.get(tag):
            self.defaultNsStack.pop()
            del self.NsDict[tag]
        
        # Check for null current elem; end of doc
        if self.currElem is None:
            self.DocumentEndEvent()
        
        # Check for parent that is None; that's
        # the top of the stack
        elif self.currElem.parent is None:
            self.ElementEvent(self.currElem)
            self.currElem = None
        
        # Anything else is just some element in the current
        # packet wrapping up
        else:
            self.currElem = self.currElem.parent
    
    def data(self, data):
        print 'data', data
        data = data.strip()
        if self.currElem != None:
            self.currElem.addContent(data)
        
    
    def comment(self, *data):
        print 'comment', data
    
    def close(self):
        print("close")

class LXMLElementStream:
    def __init__(self):
        self.DocumentStartEvent = None
        self.ElementEvent = None
        self.DocumentEndEvent = None
        self.cb = {"start": self.start, "end": self.end, "start-ns": self.start_ns, "end-ns": self.end_ns}
        self.events = self.cb.keys()
        self.currElem = None
        self.defaultNsStack = ['']
        self.documentStarted = 0
        self.localPrefixes = {}
    
    def parse(self, data):
        try:
            for action, element in etree.iterparse(BytesIO(data), events=self.events, resolve_entities=False, remove_blank_text=True):
                self.cb[action](element)
        except Exception as e:
            raise ParseError, str(e)
    
    def start(self, data):
        print 'start', data
        
        tag = etree.QName(data.tag)
        qname = ('', tag.localname) if tag.namespace is None else (tag.namespace, tag.localname) 

        #=======================================================================
        # for k, v in attrs.items():
        #     if " " in k:
        #         aqname = k.rsplit(" ", 1)
        #         attrs[(aqname[0], aqname[1])] = v
        #         del attrs[k]
        #=======================================================================

        # Construct the new element
        e = Element(qname, self.defaultNsStack[-1], data.attrib, self.localPrefixes)
        
        #Add content
        if data.text:
            e.addContent(data.text)
        
        self.localPrefixes = {}

        # Document already started
        if self.documentStarted == 1:
            if self.currElem != None:
                self.currElem.children.append(e)
                e.parent = self.currElem
            self.currElem = e

        # New document
        else:
            self.documentStarted = 1
            self.DocumentStartEvent(e)
    
    def end(self, data):
        print 'end', data
        # Check for null current elem; end of doc
        if self.currElem is None:
            self.DocumentEndEvent()

        # Check for parent that is None; that's
        # the top of the stack
        elif self.currElem.parent is None:
            self.ElementEvent(self.currElem)
            self.currElem = None

        # Anything else is just some element in the current
        # packet wrapping up
        else:
            self.currElem = self.currElem.parent
    
    def start_ns(self, ns):
        print 'start_ns', ns
        
        prefix, uri = ns
        if prefix:
            self.localPrefixes[prefix] = uri
        else:
            self.defaultNsStack.append(uri)
    
    def end_ns(self, prefix):
        print 'end_ns', prefix
        if prefix is None:
            self.defaultNsStack.pop()
        

class LXMLElementStreamTest:
    def __init__(self):
        self.DocumentStartEvent = None
        self.ElementEvent = None
        self.DocumentEndEvent = None
        self.cb = {"start": self.start, "end": self.end, "start-ns": self.start_ns, "end-ns": self.end_ns}
        self.events = self.cb.keys() 
        self.parser = etree.XMLParser(resolve_entities=False, ns_clean=False, target=self, recover=True)
        self.currElem = None
        self.defaultNsStack = ['']
        self.documentStarted = 0
        self.localPrefixes = {}

    def parse(self, f):
        try:
            for action, element in etree.iterparse(BytesIO(f), events=self.events, resolve_entities=False, encoding='utf-8'):
                self.cb[action](element)
        except Exception as e:
            raise ParserError, str(e)

    def start(self, *Element):
        print 'start', Element

    def end(self, *tag):
        print 'end', tag

    def data(self, data):
        print 'data', data
        if self.currElem != None:
            self.currElem.addContent(data)
    
    def comment(self, tag):
        print 'comment', tag
    
    def close(self):
        print 'close'
    
    
    def start_ns(self, *element):
        print 'start_ns', element


    def end_ns(self, value):
        print 'end_ns', value

if __name__ == '__main__':
    
    def docStartEvent(element):
        print "docStartEvent", element.toXml()
    
    def elementEvent(element):
        print "ElementEvent", element.toXml()
    
    def documentEndEvent():
        print "documentEndEvent"
    
    s = '''<?xml version="1.0" encoding="utf-8"?>
    <stream:stream from="gmail.com" id="FCD1F11D3C9FBE85" version="1.0" xmlns:stream="http://etherx.jabber.org/streams" xmlns="jabber:client">
    <stream:features>
    <starttls xmlns="urn:ietf:params:xml:ns:xmpp-tls"><required/></starttls>
    <mechanisms xmlns="urn:ietf:params:xml:ns:xmpp-sasl"><mechanism>X-OAUTH2</mechanism><mechanism>X-GOOGLE-TOKEN</mechanism></mechanisms>
    </stream:features>
    </stream:stream>'''
    
    parsers = [(LXMLElementStreamTest, s), (LXMLElementStream, s), (LXMLFeedParserStream, s), (ExpatElementStream, s)]
    for parser, source in parsers:
        print 'Parsing with %s'%(parser)
        p = parser()
        p.DocumentStartEvent = docStartEvent
        p.ElementEvent = elementEvent
        p.DocumentEndEvent= documentEndEvent
        try:
            p.parse(source)
        except Exception as e:
            print 'Exception launched %s'%(e.__class__.__name__), e
        
    
    presence='''<stream:stream from="gmail.com" id="FCD1F11D3C9FBE85" version="1.0" xmlns:stream="http://etherx.jabber.org/streams" xmlns="jabber:client">
                <stream:features>
                <starttls xmlns="urn:ietf:params:xml:ns:xmpp-tls"><required/></starttls>
                <mechanisms xmlns="urn:ietf:params:xml:ns:xmpp-sasl"><mechanism>X-OAUTH2</mechanism><mechanism>X-GOOGLE-TOKEN</mechanism></mechanisms>
                </stream:features>
                <presence from="jahanzeb@gmail.com/iTeleportService.WINDOWS.B57DFBC9" to="aileensim@gmail.com/katooserv90D7F39A"><status/>
                <nick xmlns="http://jabber.org/protocol/nick">J-PC</nick><type xmlns="">WINDOWS</type><id xmlns="">vnc,rdp</id>
                <xmlns:server xmlns="http://www.w3.org/2000/xmlns/"/><server xmlns=""/><show>offline</show><invisible value="true"/><priority>-127</priority>
                <name xmlns="">iTeleportService</name><version xmlns="">6.1.0.2</version><ssh-enabled xmlns="">false</ssh-enabled><supports-dh xmlns="">false</supports-dh><rdp-username xmlns="">NT AUTHORITY\\SYSTEM</rdp-username>
                <vnc-version xmlns=""/><os-version xmlns=""/><automanage-vnc xmlns="">true</automanage-vnc><encryption-enabled xmlns="">true</encryption-enabled>
                <host-mac-address xmlns="">bc:85:56:31:8e:13</host-mac-address><router-mac-address xmlns="">40:4a:03:e9:0b:6b</router-mac-address><host-ips xmlns="">
                fe80::8fc:f77:62f2:98a7;169.254.152.167;fe80::a82b:93b7:fb01:ffa5;169.254.255.165;fe80::b40e:2c23:6056:1722;192.168.70.14;fe80::5efe:c0a8:460e;2001::5ef5:79fb:242d:1964:3f57:b9f1;fe80::242d:1964:3f57:b9f1</host-ips>
                <x xmlns="vcard-temp:x:update"><photo>3c123ca510df4b2c3cac777b94d3731a4da4f4ec</photo></x></presence>
                </stream:stream>'''
    
    p = LXMLFeedParserStream()
    p.DocumentStartEvent = docStartEvent
    p.ElementEvent = elementEvent
    p.DocumentEndEvent = documentEndEvent
    try:
        p.parse(presence)
    except Exception as e:
        print 'Exception launched %s'%(e.__class__.__name__), e
    
