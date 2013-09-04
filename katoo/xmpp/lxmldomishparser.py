'''
Created on Sep 4, 2013

@author: pvicente
'''
from lxml import etree
from twisted.words.xish import domish

def elementStream():
    return LXMLFeedParserStream()

domish.elementStream=elementStream

class LXMLFeedParserStream:
    def __init__(self):
        self.DocumentStartEvent = None
        self.ElementEvent = None
        self.DocumentEndEvent = None
        self.parser = etree.XMLParser(resolve_entities=False, ns_clean=False, remove_blank_text=True, target=self, strip_cdata=True, recover=True)
        self.currElem = None
        self.defaultNsStack = ['']
        self.NsDict=dict()
        self.documentStarted = 0
        self.localPrefixes = {}
    
    def parse(self, data):
        try:
            self.parser.feed(data)
        except Exception as e:
            raise domish.ParserError, str(e)
    
    def start(self, tag, attrib, ns):
        #print 'start', tag, attrib, ns
        
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
        e = domish.Element(qname, self.defaultNsStack[-1], attrib, self.localPrefixes)
        
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
        #print 'end', tag
        
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
        #print 'data', data
        data = data.strip()
        if self.currElem != None:
            self.currElem.addContent(data)
        
    
    def comment(self, *data):
        pass
        #print 'comment', data
    
    def close(self):
        pass
        #print("close")
