import subprocess
import signal
import re
import os

class PSLine:

        def __init__(self, line, fieldlist):
            splits = re.split(r'\s+', line)
            if len(splits) != len(fieldlist):
                raise RuntimeError("Not enough fields in PS split, got: %s" % line)
            self.__dict__.update(dict(zip(fieldlist, splits)))

        def send_signal(self, signum):
            os.kill(int(self.tid), signum)
            #signal.pthread_kill(int(self.tid), signum)

        def set_psr_mask(self, newmask):
            subprocess.check_call([
                'taskset',
                '-p',
                hex(newmask),
                self.tid],
                stderr=subprocess.PIPE, stdout=subprocess.PIPE)


        def get_psr_mask(self):
            output = subprocess.check_output([
                'taskset',
                '-p',
                self.tid],
                stderr=None).decode('ASCII').strip()

            num = (re.split(r'\s+', output))[-1]
            return int(num, base=16)

        #def __getattribute__(self, name):
            #return object.__getattribute__(self, 'fields')[name]


class PS:
    MINIMUM_FIELDS = ['pid', 'tid']
    def __init__(self, process_name=None, fields=[], threads=True):
        self.ps_cmd = ['ps', '--no-headers']
        self.fields  = list(set(PS.MINIMUM_FIELDS) | set(fields))

        if threads:
            self.ps_cmd.append('-L')

        if process_name is not None:
            if isinstance(process_name, int):
                self.ps_cmd.extend(['-p', str(process_name)])
            else:
                self.ps_cmd.extend(['-C', str(process_name)])
        else:
            self.ps_cmd.append('-e')

        self.ps_cmd.append('-o')
        self.ps_cmd.append(','.join(self.fields))

        self.process = subprocess.Popen(self.ps_cmd,
            stdout=subprocess.PIPE)

    def __iter__(self):
        def return_line():
            line = self.process.stdout.readline().strip().decode('ASCII')
            if line == '':
                return None
            else:
                return PSLine(line, self.fields)
        return iter(return_line, None)
    def __del__(self):
        self.process.communicate()



