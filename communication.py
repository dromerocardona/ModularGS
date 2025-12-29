import serial
import csv
import time
import threading
import queue
import logging
import shutil
from data import Data
from PyQt5.QtCore import QObject, pyqtSignal

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class Communication(QObject):
    telemetry_received = pyqtSignal(dict)
    lastPacketRecieved = pyqtSignal(str)

    def __init__(self, serial_port, baud_rate=115200, timeout=4, csv_filename='data.csv'):
        QObject.__init__(self)
        self.sim_thread = None
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.data_list = []
        self.reading = False
        self.csv_filename = csv_filename
        self.receivedPacketCount = 0
        self.lastPacket = ""
        self.command_queue = queue.Queue(maxsize=100)
        self.read_thread = None
        self.send_thread = None
        self.simulation = False
        self.simEnabled = False
        self.simulation_state_callback = lambda state: None

        # Load telemetry fields using Data interface
        self.data_manager = Data()
        self.loadTelemetryFields()

        try:
            self.ser = serial.Serial(self.serial_port, self.baud_rate, timeout=self.timeout)
            # Set a short write timeout to prevent blocking
            self.ser.write_timeout = 0.1
        except serial.SerialException as e:
            logging.error(f"Failed to open serial port {self.serial_port}: {e}")
            self.ser = None

        with open(self.csv_filename, mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file.tell():
                writer.writerow(self.telemetryHeaders)

    def start_communication(self, signal_emitter):
        if self.ser is None:
            print("Serial port is not available.")
            return
        self.reading = True
        self.read_thread = threading.Thread(target=self.read, args=(signal_emitter,))
        self.send_thread = threading.Thread(target=self.send_commands)
        self.read_thread.start()
        self.send_thread.start()

    def read(self, signal_emitter):
        print(f"Serial port {self.serial_port} opened successfully.")
        expected_fields = len(self.telemetryHeaders)  # Fixed number of expected CSV columns
        
        with open(self.csv_filename, mode='a', newline='') as file:
            writer = csv.writer(file)
            while self.reading:
                try:
                    # Read a full newline-terminated line (blocks until \n or timeout)
                    raw_line = self.ser.readline()
                    if not raw_line:
                        # Timeout occurred (no data for 'timeout' seconds)
                        logging.warning("Read timeout - no data received")
                        continue
                    # Decode to string and strip whitespace/newlines
                    line = raw_line.decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue  # Empty line, skip
                    self.lastPacket = line
                    try:
                        self.lastPacketRecieved.emit(line)
                    except Exception:
                        pass
                    csv_data = line.split(',')
                    if len(csv_data) != expected_fields:
                        logging.warning(f"Incomplete/malformed packet (expected {expected_fields} fields, got {len(csv_data)}): {line}")
                        continue  # Drop invalid packets
                    self.receivedPacketCount += 1
                    packet = self.parse_csv_data(line)
                    try:
                        if packet is not None:
                            self.telemetry_received.emit(packet)
                    except Exception:
                        pass
                    # Write raw row to CSV
                    writer.writerow(csv_data)
                    
                except serial.SerialException as e:
                    print(f"Serial error: {e}")
                    break  # Or handle reconnection if needed
                except Exception as e:
                    print(f"Error: {e}")

    def send_commands(self):
        """Process commands from the queue and send them at 1-second intervals."""
        last_send_time = time.time()
        while self.reading:
            try:
                # Try to get a command without blocking
                command = self.command_queue.get_nowait()
                current_time = time.time()
                # Ensure 1-second interval between sends
                if current_time - last_send_time >= 1.0:
                    start_write_time = time.time()
                    self._write_serial(command)
                    write_duration = time.time() - start_write_time
                    last_send_time = current_time
                    self.command_queue.task_done()
                    logging.debug(f"Command sent, queue size: {self.command_queue.qsize()}, write took: {write_duration:.3f}s")
                else:
                    # Put the command back if it's too soon to send
                    self.command_queue.put(command)
                    time.sleep(0.01)  # Brief sleep to prevent busy-waiting
            except queue.Empty:
                time.sleep(0.01)  # Brief sleep to prevent busy-waiting
            except Exception as e:
                logging.error(f"Error in send_commands: {e}")
                time.sleep(0.01)

    def _write_serial(self, command):
        """Helper method to write to serial port with error handling."""
        if self.ser is None or not self.ser.is_open:
            logging.error("Serial port is not available or closed")
            return
        try:
            command_to_send = f"{command}\n"
            bytes_written = self.ser.write(command_to_send.encode('utf-8'))
            if bytes_written == len(command_to_send):
                self.ser.flush()  # Ensure the command is sent
                logging.info(f"Command sent: {command}")
            else:
                logging.warning(f"Partial write for command: {command}, only {bytes_written} bytes written")
        except serial.SerialTimeoutException:
            logging.warning(f"Write timeout for command: {command}")
        except serial.SerialException as e:
            logging.error(f"Failed to send command: {e}")
        except Exception as e:
            logging.error(f"Unexpected error in _write_serial: {e}")

    def send_command(self, command):
        """Add a command to the queue."""
        try:
            self.command_queue.put(command, timeout=0.1)
            logging.debug(f"Command queued: {command}, queue size: {self.command_queue.qsize()}")
        except queue.Full:
            logging.warning("Command queue is full, dropping command")

    def flush_csv(self):
        """Flush and close the CSV file temporarily to ensure all data is written."""
        with open(self.csv_filename, mode='a', newline='') as file:
            pass

    def copy_csv(self, destination_folder):
        """Copy the CSV file to the specified destination folder."""
        if not destination_folder:
            return False
        try:
            destination_file = f"{destination_folder}/{self.csv_filename}"
            self.flush_csv()  # Ensure all data is flushed before copying
            shutil.copy(self.csv_filename, destination_file)
            logging.info(f"File copied to {destination_file}")
            return True
        except Exception as e:
            logging.error(f"Error copying file: {e}")
            return False
            return False

    def stop_communication(self):
        self.reading = False
        if self.read_thread:
            self.read_thread.join()
        if self.send_thread:
            self.send_thread.join()
        if self.ser:
            self.ser.close()
        self.flush_csv()
        print("Communication stopped.")

    def change_baud_rate(self, new_baud_rate):
        """Change the baud rate dynamically."""
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.baud_rate = new_baud_rate
        try:
            self.ser = serial.Serial(self.serial_port, self.baud_rate, timeout=self.timeout)
            print(f"Baud rate changed to {self.baud_rate}")
        except serial.SerialException as e:
            print(f"Failed to reopen serial port with new baud rate: {e}")
            self.ser = None

    def simulation_mode(self, csv_filename):
        self.simulation = True
        self.sim_thread = threading.Thread(target=self._run_simulation, args=(csv_filename,), daemon=True)
        self.sim_thread.start()

    def _run_simulation(self, csv_filename):
        """Send commands from the CSV file at 1-second intervals."""
        try:
            commands_sent = 0
            self.simulation_state_callback("Simulation: Running (0 commands sent)")
            with open(csv_filename, mode='r') as file:
                csv_reader = csv.reader(file)
                next(csv_reader, None)  # Skip header if present
                for line in csv_reader:
                    if not self.simulation:  # Stop simulation if disabled
                        break
                    if line and line[0] == 'CMD':
                        line[1] = '3195'
                        command = ','.join(line)
                        start_time = time.time()
                        self.send_command(command)  # Add to the command queue
                        commands_sent += 1
                        self.simulation_state_callback(f"Simulation: Running ({commands_sent})")
                        logging.debug(f"Simulation command prepared: {command}")
                        # Sleep to maintain 1-second interval, accounting for processing time
                        elapsed = time.time() - start_time
                        remaining = max(0, 1.0 - elapsed)
                        time.sleep(remaining)
            self.simulation_state_callback(f"Simulation: Completed")
        except FileNotFoundError:
            logging.error(f"Simulation CSV file {csv_filename} not found")
            self.simulation_state_callback("Simulation: Error (File not found)")
        except Exception as e:
            logging.error(f"Error in simulation: {e}")
            self.simulation_state_callback(f"Simulation: Error")
        finally:
            self.simulation = False
            logging.info("Simulation stopped")

    def stop_simulation(self):
        """Stop the simulation process."""
        self.simulation = False
        if getattr(self, 'sim_thread', None) is not None and self.sim_thread.is_alive():
            self.sim_thread.join()
        self.command_queue.queue.clear()

    def stop_reading(self):
        self.reading = False
        print("Reading stopped.")

    def parse_csv_data(self, data):
        csv_data = data.split(',')
        self.data_list.append(csv_data)
        self.data_list = self.data_list[-20:]

        # Map telemetryHeaders to the values in this line
        try:
            result = {}
            for idx, name in enumerate(self.telemetryHeaders):
                try:
                    val = csv_data[idx]
                except IndexError:
                    val = None
                if val is None:
                    result[name] = None
                else:
                    if name in self.numericFields:
                        try:
                            result[name] = float(val)
                        except Exception:
                            result[name] = None
                    else:
                        result[name] = val
            return result
        except Exception:
            return None

    def get_data(self):
        return self.data_list

    def get_last_packet(self):
        """Return the most recent raw packet string."""
        return getattr(self, 'lastPacket', '')

    def reset_csv(self):
        with open(self.csv_filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(self.telemetryHeaders)
    
    ## Telemetry field accessors ##

    def loadTelemetryFields(self):
        """Load telemetry headers and numeric fields from Data interface."""
        try:
            telemetry_data = self.data_manager.getTelemetryFields()
            
            # telemetryHeaders are the keys from the telemetry fields (in order)
            self.telemetryHeaders = list(telemetry_data.keys())
            
            # numericFields are fields with non-empty unit values
            self.numericFields = {
                field for field, unit in telemetry_data.items() if unit
            }
            
            logging.info(f"Loaded {len(self.telemetryHeaders)} telemetry headers from Data manager")
            logging.debug(f"Numeric fields: {self.numericFields}")
        except Exception as e:
            logging.error(f"Error loading telemetry fields: {e}")
            # Fallback to empty lists
            self.telemetryHeaders = []
            self.numericFields = set()

    def ensureFieldIndex(self):
        # build a mapping from field name to index based on telemetryHeaders
        if not hasattr(self, 'field_index') or self.field_index is None:
            self.field_index = {name: idx for idx, name in enumerate(self.telemetryHeaders)}

    def getField(self, field_name, default=None):
        # Generic getter: return latest value for telemetry field_name.
        # - Uses telemetryHeaders to map names to CSV columns.
        # - Converts to float for known numeric fields.
        # - Returns `default` on missing data or parse errors.
        
        self.ensureFieldIndex()
        idx = self.field_index.get(field_name)
        if idx is None:
            return default
        if not self.data_list:
            return default
        try:
            val = self.data_list[-1][idx]
            if field_name in self.numericFields:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return default
            return val
        except (IndexError, ValueError, TypeError):
            return default

    def __getattr__(self, name):
        #Backward-compatible dynamic getter: allow `get_<FIELD>()` calls.
        #Example: `comm.get_ALTITUDE()` will call `getField('ALTITUDE')`.

        if name.startswith('get_'):
            field = name[4:]
            self.ensureFieldIndex()
            if field in self.field_index:
                return lambda default=None: self.getField(field, default=default)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")