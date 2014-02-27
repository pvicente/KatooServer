import os
import time
import libgmail # http://libgmail.sourceforge.net/

def thread_search(ga, searchType, **kwargs):
    index = 0
    while (index == 0) or index < threadListSummary[libgmail.TS_TOTAL]:
        threadsInfo = []
        items = ga._parseSearchResult(searchType, index, **kwargs)
        try:
            threads = items[libgmail.D_THREAD]
        except KeyError:
            break
        else:
            for th in threads:
                if not type(th[0]) is libgmail.types.ListType:
                    th = [th]
                threadsInfo.append(th)
            threadListSummary = items[libgmail.D_THREADLIST_SUMMARY][0]
            threadsPerPage = threadListSummary[libgmail.TS_NUM]
            index += threadsPerPage
        yield libgmail.GmailSearchResult(ga, (searchType, kwargs), threadsInfo)

ga = libgmail.GmailAccount("pedrovfer@gmail.com", "PyL070407_")
ga.login()

for page in thread_search(ga, "query", q="is:chat"):
    print "New Page"
    time.sleep(13)
    for thread in page:
        if thread.info[0] == thread.info[10]:
            # Common case: Chats that only span one message
            filename = "chats/%s_%s.eml" % (thread.id, thread.id)
            #only download the message if we don't have it already
            if os.path.exists(filename):
                print "already have %s" % filename
                continue
            print "Downloading raw message: %s" % filename,
            message = ga.getRawMessage(thread.id).decode('utf-8').lstrip()
            print "done."
            file(filename, 'wb').write(message)
            time.sleep(13)
            continue
            # Less common case: A thread that has multiple messages
        print "Looking up messages in thread %s" % thread.id
        time.sleep(13)
        for message in thread:
            filename = "chats/%s_%s.eml" % (thread.id, message.id)
            #only download the message if we don't have it already
            if os.path.exists(filename):
                print "already have %s" % filename
                continue
            print "Downloading raw message: %s" % filename,
            file(filename, 'wb').write(message.source.lstrip())
            print "done."
            time.sleep(13)