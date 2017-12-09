import json
import logging
import logging.handlers
import os
import multicast


class Defaults:
    def __init__(self, port = "5007", timeout  = 5, log_level = "warning",ffprobe = 'ffprobe', euristic = 5):
        if port:
            self.port = port
        else:
            self.port = "5007"
            logging.info("default port set to 5007, forget to specify?")
        if timeout:
            self.timeout = timeout
        else:
            self.timeout = 5
            logging.info("default timeout set to 5, forget to specify?")
        if log_level:
            self.log_level = log_level
        else:
            self.log_level = "warning"
            logging.info("default log_level set to warning, forget to specify?")

        def which(name):
            path = os.environ.get('PATH', os.defpath)
            for d in path.split(':'):
                fpath = os.path.join(d, name)
                if os.path.exists(fpath) and os.access(fpath, os.X_OK):
                    return fpath
            return None

        if ffprobe is None:
            ffprobe = 'ffprobe'

        if '/' not in ffprobe:
            ffprobe_path = which(ffprobe) or ffprobe

        self.ffprobe = ffprobe
        self.euristic = euristic


class Channel:
    def __init__(self,channel_object,defaults):
        self.running = True
        if "name" in channel_object:
            self.name = channel_object["name"]
        if "ip" in channel_object:
            self.ip = channel_object["ip"]
        else:
            logging.warning("Channel does not have an ip, skipping")
            self.running = False
        if "port" in channel_object:
            self.port = str(channel_object["port"])
        else:
            logging.info("Channel does not have a port, fall back to default")
            if defaults.port:
                self.port = str(defaults.port)
            else:
                logging.warning(self.name + "Doesn't have default port, skipping")
                self.running = False
        self.ffprobe = defaults.ffprobe
        if "timeout" in channel_object:
            self.timeout = channel_object["timeout"]
        else:
            logging.info("Channel does not have a timeout, fall back to default")
            self.timeout = defaults.timeout
        if "euristic" in channel_object:
            self.euristic = channel_object["euristic"]
        else:
            self.euristic = defaults.euristic
        if "log_level" in channel_object:
            self.log_level = channel_object["log_level"]
            self.log_level.upper()
        else:
            logging.info("Channel does not have a logging level, fall back to default")
            self.log_level = defaults.log_level
            self.log_level.upper()
        try:
            if self.name:
                self.logger = logging.getLogger("["+self.name+"]"+self.ip+":"+self.port)
                self.loggername = "["+self.name+"]"+self.ip+":"+self.port
            else:
                self.logger = logging.getLogger(self.ip + ":" + self.port)
                self.loggername = self.ip + ":" + self.port
        except AttributeError:
            self.logger = logging.getLogger(self.ip + ":" + self.port)
            self.loggername = self.ip + ":" + self.port
        self.logger.setLevel(self.log_level)
        '''formatter = logging.Formatter('%(name)s %(levelname)-8s [%(asctime)s] %(message)s')
        filehandler = logging.FileHandler("multicastlog.log")
        filehandler.setFormatter(formatter)
        memoryhandler = logging.handlers.MemoryHandler(1024 * 10, logging.WARNING, filehandler)
        self.logger.addHandler(memoryhandler)'''

    def __str__(self):
        string = self.loggername
        try:
            for key in self.streams:
                string += str(self.streams[key])+"\n"
        except Exception:
            pass
        return string

    def probe_channel(self):
        if not self.running:
            return False
        try:
            multi = multicast.Multicast(MCAST_GRP=self.ip,
                                        MCAST_PORT=self.port,
                                        timeout=self.timeout,
                                        ffprobe_bin=self.ffprobe,
                                        loggername=self.loggername)
            #info, err = multi.probe_udp()
            #return info,err
            errors = multi.rec_and_probe()
            try:
                self.streams = multi.streams
                if not self.streams:
                    return False
            except AttributeError:
                return False
            return errors
        except Exception as err:
            logging.error("Failed channel "+ self.ip+":"+self.port + str(err))
            return False

class Configurator:
    def __init__(self,filename):
        if os.path.exists(filename):
            with open(filename) as json_file:
                try:
                    self.json_config = json.load(json_file)
                except Exception as error:
                    logging.error("Incorrect json file " + filename)
                    logging.error(error)
                    raise Exception("Incorrect json file " + filename + " " + str(error))
            try:
                self.ffmpeg_bin = self.json_config["ffmpeg_bin"]
                self.ffprobe_bin = self.json_config["ffprobe_bin"]
                if (not self.ffprobe_bin) and (not self.ffprobe_bin):
                    raise Exception("Where ffmpeg? Wont work without")
            except Exception as error:
                logging.error("FFmpeg binaries weren't found!!")
                if error:
                    logging.error(error)
                raise Exception("FFmpeg binaries weren't found!! "+str(error))
            try:
                def_port = self.json_config["port"]
                def_timeout = self.json_config["timeout"]
                def_level = self.json_config["log_level"]
                self.euristic = 5
                if "euristic" in self.json_config:
                    self.euristic = self.json_config["euristic"]
                self.defaults = Defaults(def_port, def_timeout, def_level, self.ffprobe_bin, self.euristic)
            except Exception as error:
                logging.error(error)
                raise Exception("Defaults wrong!! " + str(error))
            try:
                self.channels = self.json_config["channels"]
            except Exception as error:
                logging.error("Channels weren't found!!")
                if error:
                    logging.error(error)
                raise Exception("Channels weren't found!! " + str(error))
            '''logging.basicConfig(format='%(name)s %(levelname)-8s [%(asctime)s] %(message)s',
                                level=logging.WARNING, filename='multicastlog.log')'''

        else:
            logging.error("Critical error - can't open config in " + filename)
            raise Exception("Critical error - can't open config in " + filename)

if __name__ == '__main__':
    config = Configurator("config.json")
    for channel in config.channels:
        chan = Channel(channel,config.defaults)
        print(chan.probe_channel())