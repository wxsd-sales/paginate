import os
from datetime import datetime, timedelta

try:
    from common.mongo_db_metrics import MetricsDB
except Exception as e:
    print(e)
    from mongo_db_metrics import MetricsDB

class Report(object):

    def __init__(self):
        self.db = MetricsDB()
        self.bots = self.get_bots()

    def get_bots(self):
        retVal = {}
        bots = self.db.get_bots()
        for bot in bots:
            retVal.update({bot["id"]:bot["name"]})
        return retVal

    def get_expected_date_count(self, _from, _to, with_weekends=True):
        """
        will remove weekends and return an integer number corresponding to number of days between start_date and end_date
        purpose is to ensure we aren't skipping over any None entries from returned DB results, if no results for that date.
        """
        #start_date = datetime.strptime("2019-09-30", "%Y-%m-%d")
        start_date = datetime.strptime(_from, "%Y-%m-%d %H:%M:%S")
        end_date = datetime.strptime(_to, "%Y-%m-%d %H:%M:%S")
        num_days = 0
        while start_date <= end_date:
            if with_weekends or start_date.weekday() not in [5,6]:
                num_days += 1
            start_date += timedelta(days=1)
        return num_days

    def average_daily_active_users(self, dau_list, expected_date_count, with_weekends=True):
        sum = 0
        for dau in dau_list:
            mydate = datetime.strptime(dau['_id'], '%Y-%m-%d')
            if with_weekends or mydate.weekday() not in [5,6]:
                sum += dau["emails"]
        print("sum:{0}".format(sum))
        print("expected_date_count:{0}".format(expected_date_count))
        return sum/expected_date_count

    def write_totals(self, export_file, _from, _to, botId=None):
        if botId == None:
            all_domains = self.db.get_all_unique_domains()
            all_users = self.db.get_all_unique_users()
            unq_domains = self.db.get_all_unique_domains(_from, _to)
            unq_users = self.db.get_all_unique_users(_from, _to)
            bot_name = "all bots"
        else:
            all_domains = self.db.get_unique_domains_per_bot(botId)
            all_users = self.db.get_unique_users_per_bot(botId)
            unq_domains = self.db.get_unique_domains_per_bot(botId, _from, _to)
            unq_users = self.db.get_unique_users_per_bot(botId, _from, _to)
            bot_name = self.bots[botId]
        with open(export_file, "a") as f:
            f.write("Num Unique Domains for {0} since Metrics began (9/15/2019), {1},\n".format(bot_name, len(all_domains)))
            f.write("Num Unique Users for {0} since Metrics began (9/15/2019),{1},\n".format(bot_name, len(all_users)))
            f.write("Num Unique Domains for {0} during this time period,{1},\n".format(bot_name, len(unq_domains)))
            f.write("Num Unique Users for {0} during this time period,{1},\n".format(bot_name, len(unq_users)))
            f.write("\n")

    def write_averages(self, export_file, _from, _to, botId=None):
        if botId != None:
            dau = self.db.get_daily_active_users_per_bot(botId, _from, _to)
            bot_name = self.bots[botId]
        else:
            dau = self.db.get_daily_active_users(_from, _to)
            bot_name = "all bots"
        print(dau)
        if _to == None:
            _to = now.strftime("%Y-%m-%d %H:%M:%S")
        expected_date_count = self.get_expected_date_count(_from, _to)
        expected_date_count_wo_wknd = self.get_expected_date_count(_from, _to, False)
        avg_dau = self.average_daily_active_users(dau, expected_date_count)
        avg_dau_wo_wknd = self.average_daily_active_users(dau, expected_date_count_wo_wknd, False)
        with open(export_file, "a") as f:
            f.write("Average DAU for {0},{1},\n".format(bot_name, avg_dau))
            f.write("Average DAU for {0} (not including weekends),{1},\n".format(bot_name, avg_dau_wo_wknd))
            f.write("\n")

    def run(self, export_file, _from=None, _to=None, botId=None):
        if botId != None:
            bot_name = self.bots[botId]
        else:
            bot_name = "Totals"
        with open(export_file, "a") as f:
            f.write("\n{0},\n".format(bot_name))
        self.write_totals(export_file, _from, _to, botId)
        now = datetime.now()
        self.write_averages(export_file, _from, _to, botId)

    def get_file_name(self, start_date, end_date, export_file_path=None):
        export_file = "report{0}--{1}.csv".format(start_date.split(" ")[0], end_date.split(" ")[0])
        if export_file_path != None:
            export_file = os.path.join(export_file_path, export_file)
        return export_file

    def generate_report(self, start_date, end_date, export_file):
        with open(export_file, "w") as f:
            f.write("Time period: {0} - {1},\n\n".format(start_date, end_date))
        self.run(export_file, start_date, end_date)
        for bot in self.bots:
            if bot != 1:
                self.run(export_file, start_date, end_date, botId=bot)
        return export_file

if __name__ == "__main__":
    r = Report()
    start_date = "2019-09-15 00:00:00"
    end_date = "2019-10-09 23:59:59"#None
    export_file = r.get_file_name(start_date, end_date, "/Users/tahanson/Desktop")
    r.generate_report(start_date, end_date, export_file)
