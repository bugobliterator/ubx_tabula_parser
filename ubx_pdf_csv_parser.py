import glob
import pandas as pd
from natsort import natsorted
from StringIO import StringIO
from tabulate import tabulate
import re
class UbxCsvParser:

    TableColumns = {
        "VarType":'"",Short,Type,"Size\r(Bytes)",Comment,Min/Max,Resolution\r\n',
        "GnssID":'gnssId,GNSS\r\n',
        "MsgClass":'Name,Class,Description\r\n',
        "MsgID":'Page,Mnemonic,Cls/ID,Length,Type,Description\r\n'
    }
    #+---------+-----------------------------+-----------+------------------+-------------------+------------------+
    #| Short   | Type                        |      Size | Comment          | Min/Max           | Resolution       |
    #|         |                             |   (Bytes) |                  |                   |                  |
    #+---------+-----------------------------+-----------+------------------+-------------------+------------------|
    #| U1      | Unsigned Char               |         1 |                  | 0..255            | 1                |
    #| RU1_3   | Unsigned Char               |         1 | binary floating  | 0..(31*2^7)       | ~ 2^(Value >> 5) |
    #|         |                             |           | point with 3 bit | non-continuous    |                  |
    #|         |                             |           | exponent, eeeb   |                   |                  |
    #|         |                             |           | bbbb, (Value &   |                   |                  |
    #|         |                             |           | 0x1F) << (Value  |                   |                  |
    #|         |                             |           | >> 5)            |                   |                  |
    #| I1      | Signed Char                 |         1 | 2's complement   | -128..127         | 1                |
    #| X1      | Bitfield                    |         1 |                  |                   |                  |
    #| U2      | Unsigned Short              |         2 |                  | 0..65535          | 1                |
    #| I2      | Signed Short                |         2 | 2's complement   | -32768..32767     | 1                |
    #| X2      | Bitfield                    |         2 |                  |                   |                  |
    #| U4      | Unsigned Long               |         4 |                  | 0..4'294'967'295  | 1                |
    #| I4      | Signed Long                 |         4 | 2's complement   | -2'147'483'648 .. | 1                |
    #|         |                             |           |                  | 2'147'483'647     |                  |
    #| X4      | Bitfield                    |         4 |                  |                   |                  |
    #| R4      | IEEE 754 Single Precision   |         4 |                  | -1*2^+127 ..      | ~ Value * 2^-24  |
    #|         |                             |           |                  | 2^+127            |                  |
    #| R8      | IEEE 754 Double Precision   |         8 |                  | -1*2^+1023 ..     | ~ Value * 2^-53  |
    #|         |                             |           |                  | 2^+1023           |                  |
    #| CH      | ASCII / ISO 8859.1 Encoding |         1 |                  |                   |                  |
    #+---------+-----------------------------+-----------+------------------+-------------------+------------------+
    UbxToDsdlTypes = {
        'U1'    : 'uint8_t',
        'RU1_3' : 'uint8_t',      #currently unsupported by default in dsdl
        'I1'    : 'int8_t',
        'X1'    : 'uint8_t',
        'U2'    : 'uint16_t',
        'I2'    : 'int16_t',
        'X2'    : 'uint16_t',
        'U4'    : 'uint32_t',
        'I4'    : 'int32_t',
        'X4'    : 'uint32_t',
        'R4'    : 'float',
        'R8'    : 'double',
        'CH'    : 'char'
    }
    def __init__(self):
        self.Msgs = {}
        self.GnssId = {}
        self.ByteDefs = []
        self.ClassDict = {}
        self.VarType = {}
        self.LineCount = 0
        self.curr_msg = None
        self.parsed_msg = None
        self.curr_msg_type = ""
        self.curr_df = None
        self.new_msg = False

    def selectParser(self, line):
        for key, value in self.TableColumns.iteritems():
            if line == value:
                return key
        return ""

    def doParseGeneric(self, filename, parsetype):
        df = pd.read_csv(filename)
        if (parsetype == "VarType"):
            print tabulate(df, headers='keys', tablefmt='psql')
        elif (parsetype == "GnssID"):
            self.GnssId = df.set_index('GNSS').to_dict()["gnssId"]
        elif (parsetype == "MsgClass"):
            class_details = df.set_index('Name').to_dict('index')
            self.ClassDict.update(class_details)
        elif (parsetype == "MsgID"):
            df = df.dropna()
            msg_details = df.set_index(['Mnemonic','Type']).to_dict(orient='index')
            for key, value in sorted(msg_details.iteritems()):
                old_key = key
                key = (re.sub('[\.]', '', key[0]), re.sub('[^A-Za-z0-9]+', '', key[1]))
                msg_details[key] = value
                if key != old_key:
                    del msg_details[old_key]
            self.Msgs.update(msg_details)
        return

    def doParseMsg(self, lines, curr_msg):
        struct_field = ([line for line in lines if 'Byte Offset,"Number' in line])
        if len(struct_field):
            # print "\n", curr_msg, self.Msgs[curr_msg]['Cls/ID']
            # print "Page:", int(self.Msgs[curr_msg]['Page']), 'Length:' , self.Msgs[curr_msg]['Length']
            struct_table = '\r\n'.join(lines[lines.index(struct_field[0]):])
            df = pd.read_csv(StringIO(struct_table))
            df = df.dropna(axis='columns', how='all')
            if not self.new_msg:
                self.curr_df = self.curr_df.append(df,ignore_index=True)
            else:
                if self.parsed_msg is not None:
                    self.Msgs[self.parsed_msg]['DataFrame'] = self.curr_df
                self.curr_df = df
                self.parsed_msg = curr_msg
                self.new_msg = False
        return

    def parseFile(self, filename):
        file = open(filename, 'r')
        lines = file.readlines()
        parsetype = self.selectParser(lines[0])
        if (parsetype != ""):
            self.doParseGeneric(filename, parsetype)
        else:
            msg_name = None
            type_line = None
            if 'Message,' in lines[0]:
                #find MsgName
                prev_str = ""
                for s in self.Msgs.keys():
                    if s[0] in lines[0] and len(s[0]) > len(prev_str):
                        msg_name = s[0]
                        prev_str = s[0]
                if msg_name == None:
                    raise Exception(lines[0], "Bad MsgName")
            if msg_name:
                self.new_msg = True
                self.curr_msg = None
                #find type
                type_line = [line for line in lines if "Type," in line]
                if type_line:
                    type_line = type_line[0].split(',')
                    msg_type = re.sub('[^A-Za-z0-9]+', '', type_line[type_line.index("Type") + 1])
                    self.curr_msg = [key for key in ubx.Msgs.keys() if key[0] == msg_name and msg_type in key[1]][0]
            if self.curr_msg is not None:
                self.doParseMsg(lines, self.curr_msg)
            else:
                raise Exception(msg_name, type_line, "Bad TypeName")
        if self.parsed_msg is not None:
            self.Msgs[self.parsed_msg]['DataFrame'] = self.curr_df

ubx = UbxCsvParser()
f = natsorted(glob.glob("ubx_csv_tables/*.csv"))
for filename in f:
    print filename
    ubx.parseFile(filename)
for key in sorted(ubx.Msgs.iterkeys()):
    print key
    if ubx.Msgs[key]['Length'] != "0":
        print tabulate(ubx.Msgs[key]['DataFrame'].set_index('Name'), headers='keys', tablefmt='psql')
# print "GNSS ID"
# for key, value in ubx.GnssId.iteritems():
#     print key, value
# print "Class List"
# for key, value in ubx.ClassDict.iteritems():
#     print key, value
# print "Messages"
# for key, value in sorted(ubx.Msgs.iteritems()):
#     print key[0], '\t\t', key[1], '\t\t\t', value
