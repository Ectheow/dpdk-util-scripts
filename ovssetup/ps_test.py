import unittest
import setproctitle
import multiprocessing
import sys
import os
import time
import random
import signal 
import ps

CLEVER_NAME="clever-name{0}"
RANDOM_RANGE=[0, 100]

class ConfigurableDaemon:
    def __init__(self, name):
        self.name = name

    def start(self):
        pid = os.fork()
        if pid != 0:
            return pid
        setproctitle.setproctitle(self.name)
        os.setsid()
        sys.stdout.close()
        sys.stderr.close()
        sys.stdin.close()
        while True:
            time.sleep(1)

class TestPSList(unittest.TestCase):
    def test_has_pid(self):
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
        name = CLEVER_NAME.format(random.randint(*RANDOM_RANGE))
        default_mask = (1<<multiprocessing.cpu_count())-1
        modified_mask = 1<<5
        ps_daemon_pid = ConfigurableDaemon(name).start()
        time.sleep(1)
        for num_alive in (1, 0):
            pslist = ps.PS(process_name=name, fields=['comm', 'tid'])
            iterator = iter(pslist)
            if num_alive > 0:
                psobj = next(iterator)
                self.assertTrue(psobj is not None)
                self.assertEqual(ps_daemon_pid, int(psobj.pid))
                self.assertEqual(default_mask, psobj.get_psr_mask())
                psobj.set_psr_mask(modified_mask)
                time.sleep(1)
                self.assertEqual(modified_mask, psobj.get_psr_mask())
                psobj.send_signal(signal.SIGINT)
                time.sleep(1)
            else:
                self.assertRaises(StopIteration, next, iterator)



if __name__ == '__main__':
    unittest.main()

