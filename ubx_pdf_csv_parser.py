import glob
import pandas as pd
from natsort import natsorted
from StringIO import StringIO
from tabulate import tabulate
class UBXParser:

    TableColumns = {
        "VarType":'"",Short,Type,"Size(Bytes)",Comment,Min/Max,Resolution\r\n',
        "GnssID":'gnssId,GNSS\r\n',
        "MsgClass":'Name,Class,Description\r\n',
        "MsgID":'Page,Mnemonic,Cls/ID,Length,Type,Description\r\n'
    }
    def __init__(self):
        self.Msgs = {}
        self.GnssId = {}
        self.ByteDefs = []
        self.ClassDict = {}
        self.LineCount = 0
        self.curr_msg = ""
        self.curr_msg_type = ""

    def selectParser(self, line):
        for key, value in self.TableColumns.iteritems():
            if line == value:
                return key
        return ""

    def doParseGeneric(self, filename, parsetype):
        df = pd.read_csv(filename)
        if (parsetype == "GnssID"):
            self.GnssId = df.set_index('GNSS').to_dict()["gnssId"]
        elif (parsetype == "MsgClass"):
            class_details = df.set_index('Name').to_dict('index')
            self.ClassDict.update(class_details)
        elif (parsetype == "MsgID"):
            df = df.dropna()
            msg_details = df.set_index('Mnemonic').to_dict('index')
            self.Msgs.update(msg_details)
        return

    def doParseMsg(self, lines, curr_msg, curr_msg_type):
        struct_field = ([line for line in lines if ",Byte Offset," in line])
        if struct_field:
            print "\n", curr_msg, curr_msg_type, self.Msgs[curr_msg]['Cls/ID'] 
            struct_table = '\r\n'.join(lines[lines.index(struct_field[0]):])
            df = pd.read_csv(StringIO(struct_table))
            df = df.dropna(axis='columns', how='all')
            print tabulate(df, headers='keys', tablefmt='psql')
        return

    def parseFile(self, filename):
        file = open(filename, 'r')
        lines = file.readlines()
        parsetype = self.selectParser(lines[0])
        if (parsetype != ""):
            self.doParseGeneric(filename, parsetype)
        else:
            msg_name = [s for s in self.Msgs.keys() if s in lines[0]]
            if msg_name:
                self.curr_msg = msg_name[0]
                #find type
                type_line = [line for line in lines if ",Type," in line]
                if type_line:
                    type_line = type_line[0].split(',')
                    self.curr_msg_type = type_line[type_line.index("Type") + 1]
                    self.doParseMsg(lines, self.curr_msg, self.curr_msg_type)
            else:
                self.doParseMsg(lines, self.curr_msg, self.curr_msg_type)

ubx = UBXParser()
f = natsorted(glob.glob("ubx_csv_tables/*.csv"))
for filename in f:
    print filename
    ubx.parseFile(filename)
# print "GNSS ID"
# for key, value in ubx.GnssId.iteritems():
#     print key, value
# print "Class List"
# for key, value in ubx.ClassDict.iteritems():
#     print key, value
# print "Messages"
# for key, value in sorted(ubx.Msgs.iteritems()):
#     print key, value
