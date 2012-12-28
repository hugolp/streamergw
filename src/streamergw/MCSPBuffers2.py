from threading import Event, Lock

class MCSPConsumer(object):
    
    def __init__(self):
        self.position = 0
        

class MCSPBuffer(object):
    
    def __init__(self):
        self.buffer = bytearray()
        self.closed = False
        self.consumers = []
        self.atzero = 0
    
    def addConsumer(self, consumer):
        consumer.position = 0
        self.atzero += 1
        self.consumers.append(consumer)
    
    def removeConsumer(self, consumer):
        try:
            self.consumers.remove(consumer)
        except ValueError:
            return
        
        if consumer.position is 0:
            self.atzero -= 1
        
        if self.atzero is 0 and len(self.consumers) > 0: #in case its the last consumer that has position 0 AND in case its the last consumer
            self._trimBuffer()
    
    def read(self, consumer, size=-1):
        if size < 0:
            size = len(self.buffer)
        else:
            size = min(size, len(self.buffer))
        
        data = self.buffer[:size]
        old_position = consumer.position
        consumer.position += size
        if old_position is 0 and consumer.position is not 0:
            self.atzero -= 1
            if self.atzero <= 0:
                self._trimBuffer()
        
        return bytes(data)
    
    def _trimBuffer(self):
        position = self.consumers[0].position #_trimBuffer can only be called when there is at least one consumer
        for consumer in self.consumers[1:]:
            position = min(position, consumer.position)
        
        del self.buffer[:position]
        self.atzero = 0
        for consumer in self.consumers:
            consumer.position -= position
            if consumer.position <= 0:
                self.atzero += 1
    
    def write(self, data):
        if not self.closed:
            self.buffer.extend(data)
    
    def close(self):
        self.closed = True
    
    @property
    def length(self):
        return len(self.buffer)


class MCSPCiruclarBuffer(MCSPBuffer):
    
    def __init__(self, size=8192*4):
        MCSPBuffer.__init__(self)
        self.size = size
    
    def write(self, data):
        if self.closed:
            return
        
        requestedlen = len(data) + len(self.buffer)
        if requestedlen > self.size:
            trim = requestedlen - self.size
            for consumer in self.consumers:
                if consumer.position > trim:
                    consumer.postion -= trim
                else:
                    consumer.position = 0 #yes, consumers cand lose data if the circular ring overrides
            del self.buffer[:trim]
        
        MCSPBuffer.write(self,data)
    
    @property
    def free(self):
        return self.buffer_size - self.length

    @property
    def is_full(self):
        return self.free == 0


"""
Right now its only safe if its operated by two threads, one for the producer and one for all the consumers.
"""
class ThreadedMCSPCircularBuffer(MCSPBuffer):
    
    def __init__(self, size=8192*4):
        MCSPBuffer.__init__(self)
        self.size = size
        self.buffer_size_usable = size
        self.buffer_lock = Lock()

        self.event_free = Event()
        self.event_free.set()
        self.event_used = Event()
    
    def removeConsumer(self, consumer):
        with self.buffer_lock:
            MCSPBuffer.removeConsumer(self, consumer)
    
    def _read(self, consumer, size=-1):
        with self.buffer_lock:
            data = MCSPBuffer.read(self, consumer, size)
            
            if not self.is_full:
                self.event_free.set()

            if self.length == 0:
                self.event_used.clear()

        return data
    
    def read(self, consumer, size=-1, block=True, timeout=None):
        if block:
            self.event_used.wait(timeout)
    
            # If the event is still not set it's a timeout
            if not self.event_used.is_set() and self.length == 0:
                raise IOError("Read timeout")
    
        return self._read(consumer, size)
    
    def write(self, data):
        data_left = len(data)
        data_total = len(data)
    
        while data_left > 0:
            self.event_free.wait()

            if self.closed:
                return

            with self.buffer_lock:
                write_len = min(self.free, data_left)
                written = data_total - data_left

                MCSPBuffer.write(self, data[written:written+write_len])

                if self.length > 0:
                    self.event_used.set()

                if self.is_full:
                    self.event_free.clear()

                data_left -= write_len

    def wait_free(self, timeout=None):
        self.event_free.wait(timeout)

    def wait_used(self, timeout=None):
        self.event_used.wait(timeout)

    def close(self):
        MCSPBuffer.close(self)

        # Make sure we don't let a .write() and .read() block forever
        self.event_free.set()
        self.event_used.set()
    
    @property
    def free(self):
        return self.buffer_size - self.length

    @property
    def is_full(self):
        return self.free == 0

