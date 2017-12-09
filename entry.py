import threading
import multiprocess
import logging
import sys

def entry_point(time):
    """
    chmod +x entry.py
    nohup /path/to/entry.py &
    or use pythonw.exe on windows
    :param time:
    :return:
    """
    threading.Timer(time, entry_point).start()  #  called every time in sec
    logging.info("Checking channels")
    multiprocess.main()

class InfiniteTimer():
    """A Timer class that does not stop, unless you want it to.
    nohup /path/to/entry.py &
    or use pythonw.exe on windows
    """

    def __init__(self, seconds, target):
        self._should_continue = False
        self.is_running = False
        self.seconds = seconds
        self.target = target
        self.thread = None
        logging.basicConfig(format='%(name)s %(levelname)-8s [%(asctime)s] %(message)s',
                            level=logging.WARNING, filename='mainthread.log')

    def _handle_target(self):
        logging.info("NOW IS RUNNING")
        self.is_running = True
        self.target()
        self.is_running = False
        logging.info("STOPPED RUNNING")
        self._start_timer()


    def _start_timer(self):
        if self._should_continue: # Code could have been running when cancel was called.
            try:
                self.thread = threading.Timer(self.seconds, self._handle_target)
                self.thread.start()
            except Exception as e:
                logging.error(str(e) + " trying to restart")
                self.thread = threading.Timer(self.seconds, self._handle_target)
                self.thread.start()

    def start(self):
        if not self._should_continue and not self.is_running:
            self._should_continue = True
            self._start_timer()
        else:
            logging.error("Timer already started or running, please wait if you're restarting.")

    def cancel(self):
        if self.thread is not None:
            self._should_continue = False # Just in case thread is running and cancel fails.
            self.thread.cancel()
        else:
            logging.error("Timer never started or failed to initialize.")
  
if __name__ == '__main__':
    #entry_point(60.0*5)  # every 5 min
    if sys.argv[1]:
        t = InfiniteTimer(60.0 * int(sys.argv[1]), multiprocess.main)
        t.start()
    else:
        t = InfiniteTimer(60.0*1, multiprocess.main)
        t.start()
