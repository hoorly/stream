from multiprocessing.dummy import Pool
import configurator
import logging,logging.handlers
from multiprocessing import cpu_count
import time
import sqlite3


def get_channel_array():
    config = configurator.Configurator("config.json")
    chan_arr = []
    for channel in config.channels:
        chan_arr.append( configurator.Channel(channel, config.defaults) )
    return chan_arr


def examine_channel(channel):
    sqlh = SQLiteHandler()
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(sqlh)
    try:
        channel.logger.addHandler(sqlh)
    except Exception as e:
        logging.warning(str(e))
    try:
        result = channel.probe_channel()
        return result,channel
    except Exception as err:
        return False,err


def logger_thread(q):
    while True:
        record = q.get()
        if record is None:
            break
        logger = logging.getLogger(record.name)
        logger.handle(record)


class SQLiteHandler(logging.Handler):
    """
    Logging handler for SQLite.

    This version sacrifices performance for thread-safety:
    Instead of using a persistent cursor, we open/close connections for each entry.

    AFAIK this is necessary in multi-threaded applications,
    because SQLite doesn't allow access to objects across threads.
    """

    initial_sql = """CREATE TABLE IF NOT EXISTS log(
                        Created text,
                        Name text,
                        LogLevel int,
                        LogLevelName text,    
                        Message text,
                        Args text,
                        Module text,
                        FuncName text,
                        LineNo int,
                        Exception text,
                        Process int,
                        Thread text,
                        ThreadName text
                   )"""

    insertion_sql = """INSERT INTO log(
                        Created,
                        Name,
                        LogLevel,
                        LogLevelName,
                        Message,
                        Args,
                        Module,
                        FuncName,
                        LineNo,
                        Exception,
                        Process,
                        Thread,
                        ThreadName
                   )
                   VALUES (
                        '%(dbtime)s',
                        '%(name)s',
                        %(levelno)d,
                        '%(levelname)s',
                        '%(msg)s',
                        '%(args)s',
                        '%(module)s',
                        '%(funcName)s',
                        %(lineno)d,
                        '%(exc_text)s',
                        %(process)d,
                        '%(thread)s',
                        '%(threadName)s'
                   );
                   """

    def __init__(self, db='channels.db'):

        logging.Handler.__init__(self)
        self.db = db
        # Create table if needed:
        conn = sqlite3.connect(self.db)
        conn.execute(SQLiteHandler.initial_sql)
        conn.commit()

    def formatDBTime(self, record):
        record.dbtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created))

    def emit(self, record):

        # Use default formatting:
        self.format(record)
        # Set the database time up:
        self.formatDBTime(record)
        if record.exc_info:
            record.exc_text = logging._defaultFormatter.formatException(record.exc_info)
        else:
            record.exc_text = ""
        # Insert log record:
        sql = SQLiteHandler.insertion_sql % record.__dict__
        conn = sqlite3.connect(self.db)
        conn.execute(sql)
        conn.commit()


def count_damage_types(errors_list):
    texture_damage = 0
    vector_damage = 0
    audio_damage = 0
    other = 0
    for error in errors_list:
        if "Invalid mb type" in error:
            texture_damage += 1
        elif "ac-tex damaged" in error:
            texture_damage += 1
        elif "slice mismatch" in error:
            texture_damage += 1
        elif "Invalid mb type" in error:
            texture_damage += 1
        elif "concealing" in error:
            texture_damage += 1
        elif "motion vector" in error:
            vector_damage += 1
        elif "00 motion_type" in error:
            vector_damage += 1
        elif "MVs not" in error:
            vector_damage += 1
        elif "[mp2" in error:
            audio_damage += 1
        elif "invalid cbp" in error:
            other += 1
        else:
            other += 1
    damage = {'texture': texture_damage,'vector':vector_damage,'audio':audio_damage,'other':other}
    return damage

def handle_euristic(damage_types, euristic = 5):
    texture_damage = ""
    vector_damage = ""
    audio_damage = ""
    other = ""
    if damage_types['texture']>euristic:
        if damage_types['texture']>3*euristic:
            texture_damage = "Текстуры повреждены"
        else:
            texture_damage = "Возможно текстуры повреждены"
    if damage_types['vector']>euristic:
        if damage_types['vector']>3*euristic:
            vector_damage = "Вектора повреждены"
        else:
            vector_damage = "Возможно вектора повреждены"
    if damage_types['audio']>euristic:
        if damage_types['audio']>3*euristic:
            audio_damage = "Аудио повреждено"
        else:
            audio_damage = "Возможно аудио повреждено"
    if damage_types['other']>euristic:
        if damage_types['other']>3*euristic:
            other = ""
        else:
            other = "Возможны ошибки неизвестного типа"

    euristic_predictions = {'texture': texture_damage, 'vector': vector_damage, 'audio': audio_damage,
                                 'other': other}
    return euristic_predictions

def display_euristic(euristic_predictions):
    string = ""
    for key in euristic_predictions:
        if euristic_predictions[key]:
            string += euristic_predictions[key]+"\n"
    return string

def euristic_string_from_res(res, euristic = 5):
    if isinstance(res, list):
        if res:
            dmg = count_damage_types(res)
            predictions = handle_euristic(dmg, euristic)
            predictions_string = display_euristic(predictions)
            if predictions_string:
                return predictions_string
        return "Ошибок не найдено"
    else:
        return "Обработка канала провалилась! Эвристику неудалось получить."

def main():
    chan_arr = get_channel_array()
    cpy = cpu_count()
    logging.info("starting with " + str(cpy) +" cpu's")
    with Pool(processes=cpy) as pool:
        result = pool.map_async(examine_channel, chan_arr)
        res_list = result.get(60*len(chan_arr)) #it's already a list
    print(res_list)
    with open("result.txt","a") as file:
        for res,chan in res_list:
            file.write(time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())+"\n"+str(chan)+"\n"+euristic_string_from_res(res,chan.euristic)+"\n")
            file.write("\n")


if __name__ == "__main__":
    start_time = time.time()
    main()
    #print(time.time() - start_time)
    logging.info("Seconds to finish" + str(time.time() - start_time) + "taken")
