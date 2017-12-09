import os
import sys
import socket
import select
from time import sleep
from time import time
import subprocess
import locale
import logging
import json

"""
[mpeg2video @ 1915FE30] ac-tex damaged at 33 22 //--what is ac-tex?

its AC coefficient errors in texture that is 8x8 dct coding.
if your stream is not damaged or truncated theres something wrong with
what is input to the decoder

"""

class Multicast:

    def __init__(self,MCAST_GRP = '224.1.1.1',
            MCAST_PORT = 5007,
            timeout = 1,
            ffmpeg_bin = "E:/Progs/ffmpeg/bin/ffmpeg",
            ffprobe_bin = "E:/Progs/ffmpeg/bin/ffprobe",
            temporal_ts = "temp.ts",
            vlevel = "warning",
            loggername="",
            MCAST_IF=False):
        self.MCAST_GRP = MCAST_GRP
        self.MCAST_PORT = MCAST_PORT
        self.MCAST_IF = MCAST_IF
        self.timeout = timeout
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin
        self.temporal_ts = temporal_ts
        self.recorded = False
        self.vlevel = vlevel
        self.loggername = loggername
        self.logger = logging.getLogger(loggername)
        self.logger.info("Initiating "+MCAST_GRP+":"+str(MCAST_PORT))
        '''logging.basicConfig(format='%(name)s %(levelname)-8s [%(asctime)s] %(message)s',
                            level=logging.WARNING, filename='multicastlog.log')'''
        self.streams = False


    def multisend(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
        sock.sendto('My multicast', (self.MCAST_GRP, self.MCAST_PORT))

    def multireceive(self, exec_time = 0):
        MCAST_PORT = int(self.MCAST_PORT)
        timeout = float(self.timeout)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            # Allow multiple sockets to use the same PORT number
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except AttributeError:
            self.logger.warning("Can't reuse socket port")
            pass
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        # Bind to the port that we know will receive multicast data
        if os.name == "nt":
            sock.bind(('', MCAST_PORT))  # in windows must bind to localhost for some reason
        else:
            sock.bind((self.MCAST_GRP, MCAST_PORT))

        if not self.MCAST_IF:
            self.logger.info("interface is not defined, setting best fit")
            # hostname of the machine where the Python interpreter is currently executing
            host = socket.gethostbyname(socket.gethostname())
            # to select the proper interface by IP address
            sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(host))
            # Tell the kernel that we want to add ourselves to a multicast group
            # The address for the multicast group is the third param
            sock.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP,
                            socket.inet_aton(self.MCAST_GRP) + socket.inet_aton(host))
        else:
            sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(self.MCAST_IF))
            sock.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP,
                            socket.inet_aton(self.MCAST_GRP) + socket.inet_aton(self.MCAST_IF))
        #  mreq = struct.pack("4sl", socket.inet_aton(self.MCAST_GRP), socket.INADDR_ANY)
        #  sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        #  dont use 4sl,better that 8bit way
        #  mreq = inet_aton(multicast_group) + inet_aton(interface_ip)
        #  s.setsockopt(IPPROTO_IP, IP_ADD_MEMBERSHIP, str(mreq))
        if not sock:
            return False
        incoming = True  # give another chance
        sock.setblocking(0)
        sock.settimeout(timeout)
        start = time()
        while 1:
            if exec_time:
                now = time()
                self.logger.debug("working for %d seconds" % (now - start))
                if (now - start) > exec_time:
                    break
            try:
                ready = select.select([sock], [], [], timeout)
                if ready[0]:
                    data, addr = sock.recvfrom(10240)
                    if data:
                        #  hexdata = binascii.hexlify(data)
                        #  print('Data = %s' % hexdata)
                        self.logger.debug("DATA INCOMING FROM " + str(addr))
                        self.logger.debug("WITH MULTICAST ADDRESS = " + self.MCAST_GRP + " : %d " % MCAST_PORT)
                        incoming = True
                    else:
                        if incoming:
                            sleep(timeout)  # it's incoming wait a second
                            incoming = False
                        else:
                            self.logger.error("No data coming")
                            self.logger.error("on " + str(addr))
                            return False
                            #break
                else:
                    if incoming:
                        sleep(timeout)
                        incoming = False
                    else:
                        self.logger.error("Nothing on multicast group located on ")
                        self.logger.error("ADDRESS = " + self.MCAST_GRP + " : %d " % MCAST_PORT)
                        return False
                        #break
            except socket.error as error:
                self.logger.error('Error occured')
                self.logger.error(error)
                return False
        return incoming

    def extractmeta(self):
        '''
        ffmpeg = subprocess.Popen([self.ffmpeg_bin, "-self.timeout", "2000",
                                   '-i', "udp://"+self.MCAST_GRP+":"+self.MCAST_PORT,
                                   "-c", "copy", "-map", "data-re", "-sself.timeout", "3000",
                                   "-f", "data", "/path/to/your/output/file"])
        '''
        #  ffmpeg -i /path/to/your/file -c copy -map data-re -f data /path/to/your/output/file
        ffprobe = subprocess.Popen([self.ffprobe_bin, "udp://"+self.MCAST_GRP+":"+str(self.MCAST_PORT)],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        procwait(ffprobe)

    def recordts(self,name=""):
        #  ffmpeg -i udp://[IP]:[PORT] -c copy /path/to/your/output/file
        #ffmpeg -i udp://225.100.100.100:5555 -acodec copy -vcodec copy -sameq -target mpegts ff-output.ts
        if not name:
            filename = self.temporal_ts
        else:
            filename = name+".ts"
        ffmpeg = subprocess.Popen([self.ffmpeg_bin, "-hide_banner", '-y', '-i',
                                   "udp://"+self.MCAST_GRP+":"+str(self.MCAST_PORT),
                                   "-c", "copy", "-t", "20",  name],
                                  stderr=subprocess.STDOUT)
        self.recorded = ffmpeg
        #procwait(ffmpeg)
        #  subprocess.call('ffmpeg -y -i udp://192.168.1.2:7777 -acodec copy output.mp3')

    def is_recorded(self):
        if self.recorded:
            if self.recorded.poll():
                return True
        return False

    def wait_for_record(self):
        starttime = time()
        while time() - starttime < 20:  #20sec
            if self.is_recorded():
                return True
            else:
                sleep(0.5)
        return True


    def spawn(self,params):
        return subprocess.Popen(params,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)


    def probe_to_json(self, fname):
        params = [self.ffprobe_bin,
                              "-hide_banner",
                              "-show_log", "48",
                              "-pretty",
                              "-loglevel", self.vlevel,
                              "-show_frames",
                              "-print_format","json",
                              "-count_frames","-count_packets",
                              '-show_format', '-show_streams', fname]
        p = self.spawn(params)
        stdout_data, ff_errors = p.communicate()
        if ff_errors:
            if self.vlevel != "error":
                self.logger.warning(ff_errors.decode('utf-8'))
        console_encoding = locale.getdefaultlocale()[1] or 'UTF-8'
        stdout_data = stdout_data.decode(console_encoding)
        #with open("test.json","w") as json:
        #    json.write(stdout_data)
        return stdout_data

    def probe_udp_tojson(self,add_params = False):
        """
        -analyzeduration 20000000 -print_format json -show_log 16 -show_frames -hide_banner -loglevel error -show_format -show_streams udp://224.1.1.1:5007?multicast=1
        :param add_params:
        :return:
        """
        fname = "udp://" + self.MCAST_GRP + ":" + str(self.MCAST_PORT)
        #info = MediaInfo(True)
        params = [self.ffprobe_bin,
            "-analyzeduration","20000000",
            #"-timeout", str(self.timeout),
            "-print_format", "json",
            "-show_log", "16",
            "-show_frames",
            "-hide_banner", "-loglevel", "error",
            '-show_format', '-show_streams', fname]
        p = self.spawn(params)
        stdout_data, ff_errors = p.communicate()
        console_encoding = locale.getdefaultlocale()[1] or 'UTF-8'
        stdout_data = stdout_data.decode(console_encoding)
        if ff_errors:
            return stdout_data, ff_errors
        else:
            return stdout_data, False

    def json_frames_errors(self,jsonstring):
        myjson = json.loads(jsonstring.replace("\\", r"\\"))
        myerrors = []
        if "frames" in myjson:
            frames = myjson["frames"]
            for frame in frames:
                if "logs" in frame:
                    myerrors.append(frame["logs"])
        if "streams" in myjson:
            self.streams = myjson["streams"]
        return myerrors

    def parse_errors(self,errors):
        crit = []
        for err_arr in errors:
            for err in err_arr:
                if "no frame" in err["message"]:
                    break
                if "non-existing PPS" in err["message"]:
                    break
                if "decode_slice_header" in err["message"]:
                    break
                if err["level"] <= 16:
                    crit.append(err["message"])
        return crit

    def log_errors(self):
        try:
            json_data, errs = self.probe_udp_tojson()
            if json_data:
                errs_list = self.json_frames_errors(json_data)
                critical_errors = self.parse_errors(errs_list)
                self.logger.warning(self.MCAST_GRP+":"+str(self.MCAST_PORT)+" "+str(critical_errors))
                with open("mytest.json", "a") as json:
                    json.write(str(critical_errors))
                return critical_errors
        except Exception as e:
            self.logger.error("error "+self.MCAST_GRP+":"+str(self.MCAST_PORT)+" "+str(e))
            return str(e)

    def rec_and_probe(self):
        """
        https://ffmpeg.org/doxygen/2.8/mpeg12dec_8c_source.html#l00734
        mpeg_decode_mb()
        libavcodec/mpeg12.c
        :return:
        """
        #is it even there??
        if not self.multireceive(2):
            logging.error("cant recieve data on "+str(self.MCAST_GRP)+":"+str(self.MCAST_PORT))
            return False
        try:
            if self.loggername:
                fname = self.loggername.replace(":","-")+".ts"
            else:
                fname = self.temporal_ts
            self.recordts(fname)
            self.wait_for_record()
            if not self.is_recorded():
                self.recorded.kill()
            if not os.path.exists(fname):
                logging.error("Didnt record or cant find" + str(self.MCAST_GRP) + ":" + str(self.MCAST_PORT))
                return False
            json_data = self.probe_to_json(fname)
            errs_list = self.json_frames_errors(json_data)
            critical_errors = self.parse_errors(errs_list)
            return critical_errors
        except Exception as e:
            logging.error(str(e))
            return False


    def probe_params(self,params):
        p = self.spawn(params)
        stdout_data, ff_errors = p.communicate()
        console_encoding = locale.getdefaultlocale()[1] or 'UTF-8'
        stdout_data = stdout_data.decode(console_encoding)
        if ff_errors:
            if self.vlevel != "error":
                self.logger.warning(ff_errors.decode('utf-8'))
        if ff_errors:
            return stdout_data, ff_errors
        else:
            return stdout_data, False




def procwait(procs):
    """
    Used to wait for process completition
    :param procs:
    can be list of processes
    or single process
    :return: nothing
    """
    if not isinstance(procs, list):
        retcode = True
        while retcode:
            try:
                retcode = procs.poll()
                sleep(.1)
            except KeyboardInterrupt:
                procs.kill()
    else:
        while procs:
            try:
                for proc in procs:
                    retcode = proc.poll()
                    if retcode is not None:  # Process finished.
                        procs.remove(proc)
                        break
                    else:  # No process is done, wait a bit and check again.
                        sleep(.1)
                        continue
            except KeyboardInterrupt:
                for proc in procs:
                    proc.kill()


if __name__ == '__main__':
    if len(sys.argv) == 3:
        if sys.argv[1] and sys.argv[2]:
            multi = Multicast(MCAST_GRP = sys.argv[1], MCAST_PORT = sys.argv[2])
        else:
            print("Error! ip port expected")
            exit()
    else:
        multi = Multicast()
    #info = multi.probe_udp()
    print(multi.rec_and_probe())
    #Dozhd.ts
    #test.mp4
    #print(err or "Critical fail!")
