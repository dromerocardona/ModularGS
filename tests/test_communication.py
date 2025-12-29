import sys
import time

# Provide a minimal PyQt5.QtCore stub if PyQt5 is not installed
if 'PyQt5' not in sys.modules:
    import types
    PyQt5 = types.ModuleType('PyQt5')
    QtCore = types.ModuleType('PyQt5.QtCore')

    class QObject:
        def __init__(self, *args, **kwargs):
            pass

    class _DummySignal:
        def __init__(self, *args, **kwargs):
            pass

        def __get__(self, obj, objtype=None):
            return self

        def emit(self, *args, **kwargs):
            # no-op
            return None

    QtCore.QObject = QObject
    QtCore.pyqtSignal = _DummySignal
    PyQt5.QtCore = QtCore
    sys.modules['PyQt5'] = PyQt5
    sys.modules['PyQt5.QtCore'] = QtCore

from communication import Communication

# Hardcoded settings
PORT = '/dev/ttyACM0'
BAUD = 9600

def main():
    comm = Communication(serial_port=PORT, baud_rate=BAUD, timeout=1, csv_filename='test_data.csv')

    # Attach simple print handlers for signals if available
    try:
        comm.telemetry_received = type('H', (), {'emit': staticmethod(lambda pkt: print('Telemetry:', pkt))})()
    except Exception:
        pass

    try:
        comm.lastPacketRecieved = type('H', (), {'emit': staticmethod(lambda p: print('Last packet:', p))})()
    except Exception:
        pass

    # Start reading (will spawn threads). If the serial port cannot be opened
    # Communication.__init__ will set ser=None and start_communication will print a message.
    comm.start_communication(signal_emitter=None)

    try:
        # Let the reader run briefly, then stop. Adjust duration as needed.
        time.sleep(10)
    except KeyboardInterrupt:
        pass

    comm.stop_communication()

if __name__ == '__main__':
    main()
