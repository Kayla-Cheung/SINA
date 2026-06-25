import sys
import codecs
import time

log_path = r'C:\Users\Kayla\.gemini\antigravity-cli\brain\5b324125-d7b0-41b7-a3b0-2c2e6d52f142\sina_v2_survival_log.md'
# Force unbuffered UTF-8 write
class Unbuffered(object):
   def __init__(self, stream):
       self.stream = stream
   def write(self, data):
       self.stream.write(data)
       self.stream.flush()
   def writelines(self, datas):
       self.stream.writelines(datas)
       self.stream.flush()
   def __getattr__(self, attr):
       return getattr(self.stream, attr)

f = codecs.open(log_path, 'w', 'utf-8')
sys.stdout = Unbuffered(f)
sys.stderr = sys.stdout

print("# SINA V2 黑暗森林法则 -- 原始数据抓包监控台\n")

import main_simulation
sim = main_simulation.SmallvilleSimulation()
sim.run_master_loop(ticks=30)
