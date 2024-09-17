#sudo apt-get install python-mysqldb
import MySQLdb
import traceback
from datetime import datetime
try:
    from common.metrics_settings import MetricsSettings
except Exception as e:
    from metrics_settings import MetricsSettings

class MetricsDB(object):
    BOT_ID = 0
    PERSON_EMAIL = 1
    DOMAIN_ID = 2
    TIMESTAMP = 3
    COMMAND = 4
    QUERY = 5

    def __init__(self):
        self.my_bot_id = MetricsSettings.metrics_bot_id
        self.metrics_table = MetricsSettings.metrics_table
        self.domains_table = MetricsSettings.domains_table
        self.bots_table    = MetricsSettings.bots_table

    def connect(self):
        return MySQLdb.connect(host=MetricsSettings.db_hostname,
                               user=MetricsSettings.user,
                               passwd=MetricsSettings.password,
                               db=MetricsSettings.db_name,
                               ssl={'ca': MetricsSettings.ca_path})

    def insert(self, personEmail, command, query=None):
        ret_val = False
        domain = personEmail
        try:
            try:
                user, domain = personEmail.split("@",1)
            except Exception as e:
                print("personEmail split exception in metrics framework:{0}".format(e))
            time_stamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

            base_insert_stmnt = "INSERT INTO {0} (botId, personEmail, domainId, time_stamp, command, query) ".format(self.metrics_table)
            conn = self.connect()
            c = conn.cursor()
            try:
                try:
                    insert_stmnt = base_insert_stmnt + "VALUES (%s,%s,(SELECT id FROM {0} WHERE name='{1}'),%s,%s,%s);".format(self.domains_table, domain)
                    c.execute(insert_stmnt, (self.my_bot_id, personEmail, time_stamp, command, query))
                    last_id = conn.insert_id()
                    conn.commit()
                    ret_val = True
                except MySQLdb._exceptions.OperationalError as ex:
                    print(ret_val)
                    if ex.args[0] == 1048 and "Column 'domainId' cannot be null" in ex.args[1]:
                        conn.close()
                        print("Domain {0} not found, adding and retrying...".format(domain))
                        domainId = self.insert_domain(domain)
                        print("Domain inserted. ID:{0}".format(domainId))
                        conn = self.connect()
                        c = conn.cursor()
                        insert_stmnt = base_insert_stmnt + "VALUES (%s,%s,%s,%s,%s,%s);"#.format(self.domains_table)
                        c.execute(insert_stmnt, (self.my_bot_id, personEmail, domainId, time_stamp, command, query))
                        last_id = conn.insert_id()
                        conn.commit()
                        ret_val = True
                    else:
                        traceback.print_exc()
                        print("Operational Error, but I don't know how to handle! {0}".format(ex))
            except Exception as e:
                traceback.print_exc()
                print("Insert metrics exception: {0}".format(e))
            conn.close()
        except Exception as exx:
            traceback.print_exc()
            print("Metrics General Insert Exception: {0}".format(exx))
        return ret_val

    def insert_domain(self, domain):
        conn = self.connect()
        c = conn.cursor()
        last_id = None
        try:
            insert_stmnt = "INSERT INTO {0} (name) VALUES (%s)".format(self.domains_table)
            c.execute(insert_stmnt, (domain,))
            last_id = conn.insert_id()
            conn.commit()
            ret_val = True
        except Exception as e:
            print("Insert domain exception: {0}".format(e))
        conn.close()
        return last_id

    def get_unique_users_per_bot(self, botId, _from=None, _to=None):
        result = None
        try:
            conn = self.connect()
            c = conn.cursor()
            values = (botId,)
            select_stmt = "SELECT DISTINCT m.personEmail FROM {0} as m ".format(self.metrics_table)
            select_stmt += "WHERE m.botId = %s "
            print(_from)
            print(_to)
            if _from != None:
                select_stmt += "AND m.time_stamp >= %s "
                if _to != None:
                    select_stmt += "AND m.time_stamp <= %s "
                    values = (botId, _from,_to,)
                else:
                    values = (botId, _from)
            elif _to != None:
                select_stmt += "AND m.time_stamp <= %s "
                values = (botId, _to)
            print("select_stmt:{0}".format(select_stmt))
            print("values:{0}".format(values))
            c.execute(select_stmt, values)
            result = c.fetchall()
            conn.close()
        except MySQLdb.ProgrammingError as e:
            print("get_unique_users_per_bot error: {0}".format(e))
        return result

    def get_all_unique_users(self, _from=None, _to=None):
        result = None
        try:
            conn = self.connect()
            c = conn.cursor()
            values = None
            select_stmt = "SELECT DISTINCT m.personEmail FROM {0} as m ".format(self.metrics_table)
            print(_from)
            print(_to)
            if _from != None:
                select_stmt += "WHERE m.time_stamp >= %s "
                if _to != None:
                    select_stmt += "AND m.time_stamp <= %s "
                    values = (_from,_to,)
                else:
                    values = (_from,)
            elif _to != None:
                select_stmt += "WHERE m.time_stamp <= %s "
                values = (_to,)
            print("select_stmt:{0}".format(select_stmt))
            print("values:{0}".format(values))
            if values != None:
                c.execute(select_stmt, values)
            else:
                c.execute(select_stmt)
            result = c.fetchall()
            conn.close()
        except MySQLdb.ProgrammingError as e:
            print("get_all_unique_users error: {0}".format(e))
        return result

    def get_unique_domains_per_bot(self, botId, _from=None, _to=None):
        result = None
        try:
            conn = self.connect()
            c = conn.cursor()
            values = (botId,)
            select_stmt = "SELECT DISTINCT m.domainId, d.name, m.botId FROM {0} as m ".format(self.metrics_table)
            select_stmt += "INNER JOIN {0} as d on d.id = m.domainId ".format(self.domains_table)#INNER JOIN because we don't want None domains
            select_stmt += "WHERE m.botId = %s "
            print(_from)
            print(_to)
            if _from != None:
                select_stmt += "AND m.time_stamp >= %s "
                if _to != None:
                    select_stmt += "AND m.time_stamp <= %s "
                    values = (botId,_from,_to,)
                else:
                    values = (botId,_from)
            elif _to != None:
                select_stmt += "AND m.time_stamp <= %s "
                values = (botId,_to)
            print("select_stmt:{0}".format(select_stmt))
            print("values:{0}".format(values))
            c.execute(select_stmt, values)
            result = c.fetchall()
            conn.close()
        except MySQLdb.ProgrammingError as e:
            print("get_unique_domains_per_bot error: {0}".format(e))
        return result

    def get_all_unique_domains(self, _from=None, _to=None):
        result = None
        try:
            conn = self.connect()
            c = conn.cursor()
            values = None
            if _from == None and _to == None:
                select_stmt = "SELECT name FROM {0} as d".format(self.domains_table)
            else:
                select_stmt = "SELECT DISTINCT m.domainId, d.name FROM {0} as m ".format(self.metrics_table)
                select_stmt += "INNER JOIN {0} as d on d.id = m.domainId ".format(self.domains_table)#INNER JOIN because we don't want None domains
                print(_from)
                print(_to)
                if _from != None:
                    select_stmt += "WHERE m.time_stamp >= %s "
                    if _to != None:
                        select_stmt += "AND m.time_stamp <= %s "
                        values = (_from,_to,)
                    else:
                        values = (_from,)
                elif _to != None:
                    select_stmt += "WHERE m.time_stamp <= %s "
                    values = (_to,)
            print("select_stmt:{0}".format(select_stmt))
            print("values:{0}".format(values))
            if values != None:
                c.execute(select_stmt, values)
            else:
                c.execute(select_stmt)
            result = c.fetchall()
            conn.close()
        except MySQLdb.ProgrammingError as e:
            print("get_all_unique_domains error: {0}".format(e))
        return result

    def get_daily_active_users(self, _from=None, _to=None):
        result = None
        try:
            conn = self.connect()
            c = conn.cursor()
            values = None
            select_stmt = "SELECT DATE(m.time_stamp) Date, COUNT(DISTINCT m.personEmail) totalCount "
            select_stmt += "FROM {0} as m ".format(self.metrics_table)
            print(_from)
            print(_to)
            if _from != None:
                select_stmt += "WHERE m.time_stamp >= %s "
                if _to != None:
                    select_stmt += "AND m.time_stamp <= %s "
                    values = (_from,_to)
                else:
                    values = (_from,)
            elif _to != None:
                select_stmt += "WHERE m.time_stamp <= %s "
                values = (_to,)
            select_stmt += "GROUP BY DATE(m.time_stamp)"
            print("select_stmt:{0}".format(select_stmt))
            print("values:{0}".format(values))
            if values != None:
                c.execute(select_stmt, values)
            else:
                c.execute(select_stmt)
            result = c.fetchall()
            conn.close()
        except MySQLdb.ProgrammingError as e:
            print("get_daily_active_users error: {0}".format(e))
        return result

    def get_daily_active_users_per_bot(self, botId, _from=None, _to=None):
        result = None
        try:
            conn = self.connect()
            c = conn.cursor()
            values = (botId,)
            select_stmt = "SELECT DATE(m.time_stamp) Date, COUNT(DISTINCT m.personEmail) totalCount "
            select_stmt += "FROM {0} as m ".format(self.metrics_table)
            select_stmt += "WHERE m.botId = %s "
            print(_from)
            print(_to)
            if _from != None:
                select_stmt += "AND m.time_stamp >= %s "
                if _to != None:
                    select_stmt += "AND m.time_stamp <= %s "
                    values = (botId,_from,_to)
                else:
                    values = (botId,_from)
            elif _to != None:
                select_stmt += "AND m.time_stamp <= %s "
                values = (botId,_to)
            select_stmt += "GROUP BY DATE(m.time_stamp)"
            print("select_stmt:{0}".format(select_stmt))
            print("values:{0}".format(values))
            c.execute(select_stmt, values)
            result = c.fetchall()
            conn.close()
        except MySQLdb.ProgrammingError as e:
            print("get_daily_active_users_per_bot error: {0}".format(e))
        return result

    def get_command_count(self, command, _from=None, _to=None):
        result = None
        try:
            conn = self.connect()
            c = conn.cursor()
            values = (self.my_bot_id,command)
            select_stmt = "SELECT COUNT(*) "
            select_stmt += "FROM {0} as m ".format(self.metrics_table)
            select_stmt += "WHERE m.botId = %s AND m.command = %s "
            print(_from)
            print(_to)
            if _from != None:
                select_stmt += "AND m.time_stamp >= %s "
                if _to != None:
                    select_stmt += "AND m.time_stamp <= %s "
                    values = (self.my_bot_id,command,_from,_to)
                else:
                    values = (self.my_bot_id,command,_from)
            elif _to != None:
                select_stmt += "AND m.time_stamp <= %s "
                values = (self.my_bot_id,command,_to)
            #select_stmt += "GROUP BY DATE(m.time_stamp)"
            print("select_stmt:{0}".format(select_stmt))
            print("values:{0}".format(values))
            c.execute(select_stmt, values)
            result = c.fetchone()[0]
            conn.close()
        except MySQLdb.ProgrammingError as e:
            print("get_command error: {0}".format(e))
        return result

    def get_bots(self):
        result = None
        try:
            conn = self.connect()
            c = conn.cursor()
            select_stmt = "SELECT * FROM {0};".format(self.bots_table)
            print("select_stmt:{0}".format(select_stmt))
            c.execute(select_stmt)
            result = c.fetchall()
            conn.close()
        except MySQLdb.ProgrammingError as e:
            print("get_bots error: {0}".format(e))
        return result

    def print_unique_domains(self, _from=None, _to=None):
        all_domains = self.get_all_unique_domains(_from, _to)
        print(all_domains)
        print("Num Domains:{0}".format(len(all_domains)))

    def print_unique_domains_per_bot(self, botId, _from=None, _to=None):
        all_domains = self.get_unique_domains_per_bot(botId, _from, _to)
        print(all_domains)
        print("Num Domains:{0}".format(len(all_domains)))

    def print_unique_users(self, _from=None, _to=None):
        all_users = self.get_all_unique_users(_from, _to)
        print(all_users)
        print("Num Users:{0}".format(len(all_users)))

    def print_unique_users_per_bot(self, botId, _from=None, _to=None):
        all_users = self.get_unique_users_per_bot(botId, _from, _to)
        print(all_users)
        print("Num Users:{0}".format(len(all_users)))

    def print_daily_active_users(self, _from=None, _to=None):
        dau = self.get_daily_active_users(_from, _to)
        print(dau)
        print("Num Days:{0}".format(len(dau)))

    def print_daily_active_users_per_bot(self, botId, _from=None, _to=None):
        dau = self.get_daily_active_users_per_bot(botId, _from, _to)
        print(dau)
        print("Num Days:{0}".format(len(dau)))

if __name__ == "__main__":
    import time
    rdb = MetricsDB()
    rdb.insert('matthias.blaesing@tu-dortmund.de', 'testing', None)
    #testPersonEmail = "test@newexample3.com"
    #command = "test3"
    #query = "this is a test3"
    #print(rdb.insert(testPersonEmail, command, query))
    #rdb.print_unique_domains()
    #rdb.print_unique_domains("2019-09-12 00:00:00", "2019-10-03 00:00:00")
    #rdb.print_unique_domains("2019-09-25 00:00:00")
    #rdb.print_unique_domains(_to="2019-09-25 00:00:00")

    #rdb.print_unique_domains_per_bot(4)
    #rdb.print_unique_domains_per_bot(4, "2019-09-12 00:00:00", "2019-10-03 00:00:00")
    #rdb.print_unique_domains_per_bot(4, "2019-09-25 00:00:00")
    #rdb.print_unique_domains_per_bot(4, _to="2019-09-25 00:00:00")

    #rdb.print_unique_domains_per_bot(12)
    #rdb.print_unique_domains_per_bot(12, "2019-09-12 00:00:00", "2019-10-04 00:00:00")
    #rdb.print_unique_domains_per_bot(12, "2019-09-25 00:00:00")
    #rdb.print_unique_domains_per_bot(12, _to="2019-09-25 00:00:00")

    #rdb.print_unique_users()
    #rdb.print_unique_users("2019-09-12 00:00:00", "2019-10-03 00:00:00")
    #rdb.print_unique_users("2019-09-25 00:00:00")
    #rdb.print_unique_users(_to="2019-09-25 00:00:00")

    #rdb.print_unique_users_per_bot(4)
    #rdb.print_unique_users_per_bot(4, "2019-09-12 00:00:00", "2019-10-03 00:00:00")
    #rdb.print_unique_users_per_bot(4, "2019-09-25 00:00:00")
    #rdb.print_unique_users_per_bot(4, _to="2019-09-25 00:00:00")

    #rdb.print_unique_users_per_bot(12)
    #rdb.print_unique_users_per_bot(12, "2019-09-12 00:00:00", "2019-10-04 00:00:00")
    #rdb.print_unique_users_per_bot(12, "2019-09-25 00:00:00")
    #rdb.print_unique_users_per_bot(12, _to="2019-09-25 00:00:00")

    #rdb.print_daily_active_users()
    #rdb.print_daily_active_users("2019-09-12 00:00:00", "2019-10-03 00:00:00")
    #rdb.print_daily_active_users("2019-09-25 00:00:00")
    #rdb.print_daily_active_users(_to="2019-09-25 00:00:00")

    #rdb.print_daily_active_users_per_bot(12)
    #rdb.print_daily_active_users_per_bot(12, "2019-09-12 00:00:00", "2019-10-04 00:00:00")
    #rdb.print_daily_active_users_per_bot(12, "2019-09-25 00:00:00")
    #rdb.print_daily_active_users_per_bot(12, _to="2019-09-25 00:00:00")
    #rdb.print_daily_active_users_per_bot(12, _to="2019-09-18 00:00:00")
