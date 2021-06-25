"""
This module contains the code for interacting with a BnK via Python.

This package is useful if you have a Brüel & Kjær Type 3050-B-6 with a
Notar™ BZ-7848-A (LAN-XI stand-alone recorder license).

This package contains the following two functions:
    WavHeader(wav_file,verbose=False): 
        Extract metadata from a BnK produced WAV file.
    OpenWav(wav_file,verbose=False): 
        Extract times series data and metadata from a BnK produced WAV 
        file.
    
And the following class:
    Instrument
"""

import requests
import os
import time
import re
import json
from datetime import datetime as dt
import soundfile
import numpy as np

def WavHeader(wav_file, verbose=False):
    """WavHeader takes a BnK produced WAV file as input and returns a 
    dictionary containing both the WAV header information and the BnK 
    metadata.  The header data is at the beginning of the WAV file (as 
    the name suggests) and the metadata is at the end of the WAV file.

    Parameters:
        wav_file (str): The WAV file to be opened
        verbose (bool): A flag to print more information about the WAV 
                        file header and metadata (default is False)
        
    Returns:
        header (dict): Containing the header and metadata associated 
                       with the WAV file
    """

    # Read in some data from the binary file as type uint8
    # 33000 should be enough to contain the header
    dt = np.dtype('uint8')
    x = np.fromfile(wav_file, dtype=dt, count=33000) 
    
    n = 0
    header = {'ChunkID' : "".join(chr(a) for a in x[n:n+4])}
    n += 4
    header['ChunkSize'] = int.from_bytes(x[n:n+4], byteorder='little',
                                         signed=False)
    n += 4    
    header['Format'] = "".join(chr(a) for a in x[n:n+4])
    n += 4
    header['Subchunk1ID'] = "".join(chr(a) for a in x[n:n+4])
    n += 4
    header['Subchunk1Size'] = int.from_bytes(x[n:n+4], byteorder='little',
                                             signed=False)
    n += 4
    header['AudioFormat'] = int.from_bytes(x[n:n+2], byteorder='little',
                                           signed=False)
    n += 2
    header['NumChannels'] = int.from_bytes(x[n:n+2], byteorder='little',
                                           signed=False)
    n += 2
    header['SampleRate'] = int.from_bytes(x[n:n+4], byteorder='little',
                                          signed=False)
    n += 4
    header['ByteRate'] = int.from_bytes(x[n:n+4], byteorder='little',
                                        signed=False)
    n += 4
    header['BlockAlign'] = int.from_bytes(x[n:n+2], byteorder='little',
                                          signed=False)
    n += 2
    header['BitsPerSample'] = int.from_bytes(x[n:n+2], byteorder='little',
                                             signed=False)
    n += 2
    
    # The BnK puts a bunch of metadata into the WAV file
    # I don't know what ALL the metadata means, but have inferred 
    # the meaning of most of it.
    header['Meta'] = "".join(chr(a) for a in x[n:n+4])
    n += 4
    header['MetaSize'] = int.from_bytes(x[n:n+4], byteorder='little', 
                                        signed=False)
    n += 4
    n += header['MetaSize']  # Metadata seems to have a fixed size of 32716
    
    header['Subchunk2ID'] = "".join(chr(a) for a in x[n:n+4])
    n += 4
    header['Subchunk2Size'] = int.from_bytes(x[n:n+4], byteorder='little', 
                                             signed=False)
    n += 4

    # We now know how much data the WAV file contains, so we can 
    # move past the headerand the data to grab the rest of the file, 
    # which contains the metadata.
    n += header['Subchunk2Size']
    with open(wav_file, "rb") as f:
        f.seek(n, os.SEEK_SET)
        meta = f.read()
    header['ExtraBytes'] = meta
    
    if header['ExtraBytes']:
        header['Scale'] = []
        header['Sensitivity'] = []
        header['Transducer'] = []
        # Ignore the first 10 characters
        meta_list = header['ExtraBytes'][8:].split(b'\x00') 
        # Get rid of the empty bits of metadata
        meta_list = list(filter(None, meta_list)) 
        # I don't know what the first piece of metadata represents, 
        # possibly a version number, as it seems fixed a '2.10'. 
        # I am ignoring it.
        meta_index = 1 
        header['Date'] = meta_list[meta_index].decode()
        meta_index = meta_index + 1
        for x in range(header['NumChannels']):
            header['Transducer'].append(meta_list[meta_index].decode())
            meta_index = meta_index + 1
            header['Sensitivity'].append(float(meta_list[meta_index].decode()))
            meta_index = meta_index + 6
            header['Scale'].append(float(meta_list[meta_index].decode()))
            meta_index = meta_index + 4
        header['UnitName'] = meta_list[meta_index].decode()
        meta_index = meta_index + 1
        header['Label'] = meta_list[meta_index].decode().split(":",1)[1]
        # Remove UTC info, and blank space at start of label
        UTC_info = '. Recording date/time is in UTC.'
        header['Label'] = header['Label'][1:].replace(UTC_info,'')
        meta_index = meta_index + 2
        setup_string = meta_list[meta_index].decode()
        header['ChannelUnits'] = []
        header['ChannelNames'] = []   
        for i in range(header['NumChannels']):
            info_start = setup_string.find('[Channel {}]'.format(i+1))
            setup_string = setup_string[info_start+12:]
            info_stop = setup_string.find('[')
            channel_info = setup_string[:info_stop]
            header['ChannelUnits'].append(
                channel_info.split('Unit=')[1].split('\n',1)[0])
            header['ChannelNames'].append(
                channel_info.split('Name=')[1].rsplit('\n',1)[0])

    else:
        if verbose:
            print("File does not contain extra data.")

    if verbose:
        print("Header info for {}".format(wav_file))
        for key in header:
            print(key, ' : ', header[key])
        print()

    return header

def OpenWav(wav_file,verbose=False,start=0,stop=None):
    """This function opens a BnK created WAV file.
    
    Parameters:
        wav_file (str): The WAV file to be opened
        verbose (bool): A flag to print more information about the
                        WAV file (default is False).
        start (int) :   Index of the first value to retrieve
        stop (int) :    Index of the last value to retrieve
        
    Returns:
        wav_data (ndarray): Containing scaled times series data for
                            each channel in the WAV file. 
        header (dict):      Containing the header and metadata 
                            associated with the WAV file
        json_data (dict):   Containing the settings dictionary used by
                            the bnk device during recording
    """
    
    header = WavHeader(wav_file, verbose)

    wav_data, sr = soundfile.read(wav_file, always_2d=True, 
                                  start=start,stop=stop)
    
    for x in range(header['NumChannels']):
        # The scale factor already incorporates the sensitivity
        wav_data[:,x] = header['Scale'][x] * wav_data[:,x]

    json_file = wav_file[:-3] + "json"
    if os.path.isfile(json_file):
        with open(json_file, 'r') as f:
            json_data = json.loads(f.read())
    else:
        json_data = None
    
    if verbose:
        print("{} contains {} channels, extracting {} samples per channel.".format(
            wav_file, wav_data.shape[1], wav_data.shape[0]))
        print()
        print(json_data)
    
    return wav_data, header, json_data

class Instrument(object):
    """A class used to represent a BnK device.
    
    Parameters:
        bnk_ip (str)     : The ip address of the BnK device    
    
    Attributes:
        info (dict)      : Summary of status of BnK device at last query
        settings (dict)  : Channel settings to be used for next recording
        recordings (list): List of recordings on the BnK device
        ip (str)         : The ip address of the BnK device
        base_url (str)   : The URL of the BnK device
        header (dict)    : TCP/IP header, which allows communication with
                           the BnK
        last_change (int): Count of the number of calls to the BnK device
        
    Methods:
        open():
            Open the recorder application on the BnK device
        close():
            Close the recorder application on the BnK device
        reboot():
            Reboot the BnK device
        transducers():
            Returns a list of the current transducers (not currently used)
        show_settings(display,settings):
            Display the settings to be used for the next recording or a 
            given dictionary
        status(verbose):
            Get a status update
        powerup():
            Prepare the BnK device for recording
        record(record_length=1):
            Record for {record_length} seconds
        start_record():
            Begin recording
        stop_record():
            Stop recording
        powerdown():
            Power down powered devices and turn off recording mode
        get_settings(measurement=0):
            Get the settings from a previous recording
        get_wav(measurement=0,directory='',recording_id=''):
            Download the WAV file associated with a recording
        delete_recording(measurement=0,recording_id=''):
            Delete a recording from the BnK device
        delete_all(checkstr):
            Delete ALL recordings from the BnK device
        disable_all():
            Disable all channels
        disable_channel(channel=1):
            Disable a channel
        enable_channel(channel=1):
            Enable a channel
        set_samplerate(sample_rate):
            Set the sample rate for all channels
        set_channel():
            Set the parameter for a chennel
        set_name(name): 
            Set the name for the next recording
    """
    
    def __init__(self,bnk_ip):
        self.base_url = 'http://{}/'.format(bnk_ip)
        self.ip = bnk_ip

        self.header = {
            'Accept': ('text/html.application/xhtml+xml,'
                       'application/xml;q=0.9,*/*;q-0.8'),
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'host': self.ip,
            'If-Modified-Since': 'Sat, 1 Jan 2005 00:00:00 GMT',
            'Referer': self.base_url + 'recorder',
            'User-agent': 'Firefox',
             }
        
        self.status()
                  
        # Set the time
        now_str = str(int(time.mktime(
            dt.now().timetuple()))*1000)
        z = self.header.copy()
        z.update({'Content-Length': "{}".format(len(now_str)),
                  'Content-Type': 'text/plain; charset=UTF-8'})
        try:
            response = requests.put(self.base_url + 'rest/rec/module/time',
                                    headers=z,data=now_str)
        except:
            print("There appears to be no BnK device connected.")
            return

        if self.state == 'Idle':
            self.open()

        # Get some info from the B & K
        response = requests.get(self.base_url + 'rest/rec/module/info', 
                                headers=self.header)
        self.info = json.loads(response.text)

        # Get some info about the default settings
        response = requests.get(self.base_url 
                                + 'rest/rec/channels/input/default', 
                                headers=self.header)
        self.settings = json.loads(response.text)

        # Get the list of recordings
        self.list_recordings(quiet=True)        
        
    def __str__(self):
        """Produces a string with various info about an instrument."""

        out_str = f"""
BnK Properties:
    {self.info['numberOfInputChannels']} channels
    SD card is{'' if self.info['sdCardInserted'] else ' not'} inserted
    Filters      : {self.info['supportedFilters']}
    SampleRates  : {self.info['supportedSampleRates']}        
    Ranges       : {self.info['supportedRanges']}

""" 
        syntax_buy_fix = '"""'
        out_str += self.show_settings(False)
        out_str += self.status(False)
        
        return out_str

    def __check_string(self,test_string):
        """Check for potentially corrupting characters.

        I don't know exactly which characters are allowed for labels
        in the BnK device, so I will be conservative and only allow
        the following:
                a-z, A-Z, 0-9, '-', '_', ' ' and '.'
        """
        if re.search(r'[^a-zA-Z0-9\-_\ \.]', test_string):
            raise Exception("Strings can only contain a-z, "
                            "A-Z, 0-9, '-', '_', ' ' and '.'")
        return test_string

    def reboot(self):
        """Reboot the BnK device"""

        z = self.header.copy()
        z.update({'Content-Length': '0', 'Pragma': 'no-cache'})
        response = requests.post(self.base_url, headers=z, data={'reboot' : 1}) 

    def open(self):
        """Open the recorder application on the BnK device"""
        
        self.status(False)
        
        if self.state != 'Idle':
            raise Exception(f"BnK must be in state 'Idle' to be opened.\n"
                           f"\t\tIt is currently in state {self.state}")

        z = self.header.copy()
        z.update({'Content-Length': '0', 'Content-Type': 'text/plain'})
        response = requests.put(self.base_url + 'rest/rec/open',headers=z)
        
        self.status()
        
    def close(self):
        """Close the recorder application on the BnK device"""
        
        if self.state != 'RecorderOpened':
            raise Exception(f"BnK must be in state 'RecorderOpened' "
                           f"to be closed.\n"
                           f"\t\tIt is currently in state {self.state}")
            
        # Close the recorder application
        z = self.header.copy()
        z.update({'Content-Length': '0', 'Content-Type': 'text/plain'})
        response = requests.put(self.base_url + 'rest/rec/close',headers=z)
        
        self.status()
        
    def transducers(self):
        """Returns a list of the current transducers (not currently used)
        
        Returns:
            list : A list of the transducers for each channel
        """
        
        response = requests.get(self.base_url 
                                + 'rest/rec/channels/input/all/transducers',
                                headers=self.header)
        return json.loads(response.text)
        
    def show_settings(self,display=True,settings=False):
        """Display the settings to be used for the next recording or
        a given dictionary
        
        Parameters
            display (bool): If True, this prints the the current settings
            settings (bool or dict) : If False, use self settings, 
                                      otherwise use settings
        """
        
        if not settings:
            settings = self.settings

        sr = { '51.2 kHz' : 131072, '25.6 kHz' : 65536, '12.8 kHz' : 32768, 
              '6.4 kHz' : 16384, '3.2 kHz' : 8192, '1.6 kHz': 4096 }
        out_str = "\t{}\n".format(settings['name'])
        for idx,channel in enumerate(settings['channels']):
            if channel['enabled']:
                if channel['ccld']:
                    powered = ", Powered."
                else:
                    powered = "."
                out_str += ("\tChannel {} : {}\n\t\t{} SPS, {} filter, "
                            "{}, {}V/{}{}\n").format(
                                idx+1,
                                channel['name'],
                                sr[channel['bandwidth']],
                                channel['filter'],
                                channel['range'],
                                channel['transducer']['sensitivity'],
                                channel['transducer']['unit'],
                                powered,
                                )
        if display:
            print(out_str)
            return
        else:
            return out_str
                
    def status(self, verbose=True):
        """Get a status update.
        
        Parameters:
            verbose (bool) : Print status
            
        """

        response = requests.get(self.base_url + 'rest/rec/onchange?last=' 
                                + str(0), headers=self.header)
        status_info = json.loads(response.text)
        self.last_change = status_info['lastUpdateTag']
        self.state = status_info['moduleState']
        
        current_status = (f"\n\tBnK state : {self.state}\n"
                          f"\tcommands sent : {self.last_change}\n"
                          f"\tBnK clock : {response.headers['Date']}"
                         )
        if verbose:
            print(current_status)
        else:
            return current_status

    def powerup(self):
        """Prepare the BnK for recording"""
        
        settings = json.dumps(self.settings)

        self.status()
        if self.state != 'RecorderOpened':
            raise Exception(f"BnK must be in state 'RecorderOpened' "
                           f"to be configured.\n"
                           f"\t\tIt is currently in state {self.state}")

        z = self.header.copy()
        z.update({'Content-Length': '0', 'Content-Type': 'text/plain'})
        response = requests.put(self.base_url + 'rest/rec/create',headers=z)
        
        self.status()

        # Create the new recording
        z = self.header.copy()
        z.update({'Content-Length': f"{len(settings)}",
                  'Content-Type': 'text/plain; charset=UTF-8'})
        response = requests.put(self.base_url + 'rest/rec/channels/input',
                                headers=z, data=settings)
        #print(response)
        time.sleep(0.1)
        
        response = requests.get(self.base_url + 'rest/rec/channels/input',
                                headers=self.header)
        settings = json.loads(response.text)
        self.status()
        return settings
        
    def record(self,record_length=1):
        """Record for a specified length of time
        
        Parameters:
            record_length (int) : in seconds (default: 1)
            
        Returns:
            recordingUri (str) : The URI needed to access the recording
        """
                
        if self.state != 'RecorderStreaming':
            raise Exception(f"BnK must be in state 'RecorderStreaming' "
                           f"to record.\n"
                           f"\t\tIt is currently in state {self.state}")

        # Press the start button, and get the recording URI
        z = self.header.copy()
        z.update({'Content-Length': '0', 'Pragma': 'no-cache'})
        response = requests.post(self.base_url + 'rest/rec/measurements',
                                 headers=z, data="")
        recordingUri = response.text
        print("The recording uri is : " + self.base_url + recordingUri)
        self.status()
                
        # Record for some time
        time.sleep(record_length)

        z = self.header.copy()
        z.update({'Content-Length': '0', 'Content-Type': 'text/plain'})
        response = requests.put(self.base_url + recordingUri + "/stop",
                                headers=z)
        self.status()
        
        return recordingUri[-10:]

    def start_record(self):
        """Start the BnK device recording"""
                
        if self.state != 'RecorderStreaming':
            raise Exception(f"BnK must be in state 'RecorderStreaming' "
                           f"to record.\n"
                           f"\t\tIt is currently in state {self.state}")

        # Press the start button, and get the recording URI
        z = self.header.copy()
        z.update({'Content-Length': '0', 'Pragma': 'no-cache'})
        response = requests.post(self.base_url + 'rest/rec/measurements',
                                 headers=z, data="")
        recordingUri = response.text
        print("The recording uri is : " + self.base_url + recordingUri)
        self.recordingUri = recordingUri
        self.status()
        return recordingUri[-10:]
                
    def stop_record(self):
        """Stop the BnK device recording"""
        
        if self.state != 'RecorderRecording':
            raise Exception(f"BnK must be in state 'RecorderRecording' "
                           f"to stop recording.\n"
                           f"\t\tIt is currently in state {self.state}")

        z = self.header.copy()
        z.update({'Content-Length': '0', 'Content-Type': 'text/plain'})
        response = requests.put(self.base_url + self.recordingUri + "/stop",
                                headers=z)
        self.status()
        
    def powerdown(self):
        """Close the BnK measurement setup (which also turns off 
        power to powered transducers).
        
        This function also updates the list of recordings associated 
        with the instrument.
        """
    
        self.status()
        
        print("Closing recorder application\n"
             "(This can take a while if there are lots of recordings)")
        
        # Finish the measurements
        z = self.header.copy()
        z.update({'Content-Length': '0', 'Content-Type': 'text/plain'})
        response = requests.put(self.base_url + 'rest/rec/finish', headers=z)
        
        self.status()
        w = 4
        print(f"Waiting {w} seconds for powerdown completion...")
        time.sleep(w)
        
        print('Updating list of recordings ...')
        self.list_recordings(quiet=True)
        
    def get_settings(self,measurement=0):
        """Retrieve the settings from a currently stored recording 
        and make them the current settings.
        
        Parameters:
            measurement (int): Which measurment in the list of recordings 
                               to retrieve (default : 0 - is a special case, 
                               meaning the last recording)
         """
    
        settings = self.recordings[measurement-1]['setup']
        self.settings = settings
    
    def get_wav(self,measurement=0,directory='',recording_id=''):
        """Download a WAV file and some json info from the BnK device
        
        Parameters:
            measurement (int): Which measurment in the list of recordings 
                               to retrieve (default : 0 - is a special case, 
                               meaning the last recording)
            directory (str):   directory in which to store the WAV file
            recording_id:      if given, this recording will be retrieved 
                               instead of a numbered recording
        
        Returns:
            wav_filename (str): A string containing the name of the 
                                retrieved WAV file."""
        
        if not self.recordings:
            print("There are no wave files to retrieve")
            return

        #Open the recordings
        z = self.header.copy()
        z.update({'Content-Length': '0', 'Content-Type': 'text/plain'})
        response = requests.put(self.base_url + 'rest/rec/open',headers=z)

        if recording_id:
            for q in self.recordings:
                if q['uri'][-10:] == recording_id :
                    x = q
                    break
        else:
            x = self.recordings[measurement-1]
        
        timestamp = dt.fromtimestamp(
            x['setup']['datetime']/1000).strftime('%Y%m%d%H%M%S')
        wav_filename = os.path.join(directory,x['setup']['name']
                                    .replace(' ','_')
                                    .replace('/','')
                                    .replace('\\','') 
                                    + "_" + timestamp)
        url = "http://" + self.ip + x['uri']
        old_filename = x['uri'].replace('/rest/rec/measurements/','')
        r = requests.get(url)
        open(wav_filename + ".wav", 'wb').write(r.content)
        open(wav_filename + ".json", 'w').write(json.dumps(x))
        time.sleep(0.01)        
        return wav_filename + ".wav"
    
    def delete_recording(self,measurement=0,recording_id=''):
        """Delete a recording from the BnK device
        
        Parameters:
            measurement (int): Which measurment in the list of recordings 
                               to retrieve (default : 0 - is a special case, 
                               meaning the last recording)
            recording_id:      if given, this recording will be retrieved 
                               instead of a numbered recording
        """
        
        if not self.recordings:
            print("There are no recordings to delete")
            return
    
        #Open the recordings
        z = self.header.copy()
        z.update({'Content-Length': '0', 'Content-Type': 'text/plain'})
        response = requests.put(self.base_url + 'rest/rec/open',headers=z)

        found = False
        if recording_id:
            for q in self.recordings:
                if q['uri'][-10:] == recording_id :
                    x = q
                    found = True
                    break
            if not found:
                print("{} does not exist".format(recording_id))
                return
        else:
            x = self.recordings[measurement-1]
            self.recordings.remove(x)
        
        z = self.header.copy()
        z.update({'Content-Length': '0', 'Content-Type': 'text/plain'})
        response = requests.delete(self.base_url + x['uri'], headers=z)
        
    def delete_all(self,check_str):
        """WARNING: This will delete all recordings off the SD card.
        
        Parameters:
            check_str (str): To make sure you are serious,
                             this variable needs to be set to "I'm sure"
        """
        if check_str == "I'm sure":
            for i in range(len(self.recordings)):
                self.delete_recording(0)
                time.sleep(0.01)
   
    def list_recordings(self,quiet=False,start=0,stop=None):
        """List all the recordings currently on the SD device
        
        Parameters:
            quiet (bool): If True, then nothing is printed
        """
        
        if self.state != 'RecorderOpened':
            raise Exception(f"BnK must be in state 'RecorderOpened' "
                           f"to list recordings.\n"
                           f"\t\tIt is currently in state {self.state}")

        # Get the list of recordings
        response = requests.get(self.base_url + 'rest/rec/measurements',
                                headers=self.header)
        recordings = json.loads(response.text)
        recordings = sorted(recordings, key=lambda x: x['setup']['datetime'] )
        self.recordings = recordings

        if not quiet:
            if start >= 0:
                shift = start
            else:
                shift = len(self.recordings) + start
            for idx, recording in enumerate(self.recordings[start:stop]):
                setup = recording['setup']
                rec_time = dt.fromtimestamp(setup['datetime']/1000)
                print(f"{idx+shift++1} : "
                      f"{rec_time.strftime('%Y-%m-%d %H:%M:%S')}, "
                      f"{recording['size']//1024} kB, "
                      f"{recording['duration']/1000} seconds")
                self.show_settings(True,setup)
            
    def disable_all(self):
        """Disable all channels for the next recording"""
        
        for x in range(self.info['numberOfInputChannels']):
            self.settings['channels'][x]['enabled'] = False
    
    def disable_channel(self,channel):
        """Disable a channel for the next recording
        
        Parameters:
            channel (int): The channel to be disabled
        """
        
        self.settings['channels'][channel-1]['enabled'] = False
    
    def enable_channel(self,channel):
        """Enable a channel for the next recording
        
        Parameters:
            channel (int): The channel to be enabled
        """
        
        self.settings['channels'][channel-1]['enabled'] = True
    
    def set_samplerate(self,sample_rate=131072):
        """Set the sample rate for all channels
        
        Parameters:
            sample_rate (int): One of [4096, 8192, 16384, 32768,
                            65536, 131072] (default: 131072)        
        """
        sr_to_bandwidth = { 
            '131072' : '51.2 kHz', 
            '65536' : '25.6 kHz', 
            '32768' : '12.8 kHz', 
            '16384' : '6.4 kHz', 
            '8192' : '3.2 kHz', 
            '4096' : '1.6 kHz',
        }
        bandwidth = sr_to_bandwidth[str(sample_rate)]
        for x in range(self.info['numberOfInputChannels']):
            self.settings['channels'][x]['bandwidth'] = bandwidth

    def set_channel(self,
                    channel=1,
                    name=False,
                    c_filter='7.0 Hz',
                    c_range='10 Vpeak',
                    sensitivity=1,
                    unit='V',
                    powered=False,
                    serialNumber='0',
                    transducerType='None'
                   ):
        """Configure the settings for a particular channel
        
        Parameters:
            channel (int)       : Integer in the range 1..6 (default: 1)
            name (str)          : Name for the channel (default: 'Channel #')
            c_filter (str)      : Type of filtering to use on the channel
                                  One of ['DC', '0.1 Hz 10%', '0.7 Hz',
                                  '1.0 Hz 10%','7.0 Hz', '22.4 Hz',
                                  'Intensity'] (default: '7.0 Hz')
            c_range (str)       : Maximum measurable voltage on the channel
                                  One of ['10 Vpeak', '31.6 Vpeak']
                                  (default: '10 Vpeak')
            sensitivity (float) : Sensitivity of the transducer (default: 1)
            unit (str)          : Units of the transducer (default: 'V')
            powered (bool)      : Does the transducer require power? 
                                  (default: False)
            serialNumber (str)  : Serial number of transducer
            transducerType (str): Type of transducer
                                
        """
        channel = channel-1
        
        if not name:
            name = "Channel {}".format(channel+1)
            
        settings = self.settings
        
        filters = ['DC', '0.1 Hz 10%', '0.7 Hz', '1.0 Hz 10%', 
                   '7.0 Hz', '22.4 Hz', 'Intensity']
        if c_filter not in filters:
            exception(f"c_filter must be one of {filters}")
        ranges = ['10 Vpeak', '31.6 Vpeak']
        if c_range not in ranges:
            exception(f"c_range must be one of {ranges}")         
        
        q = self.settings['channels'][channel]
        q['enabled'] = True
        q['name'] = self.__check_string(name)
        q['filter'] = c_filter
        q['range'] = c_range
        q['ccld'] = bool(powered)
        q = self.settings['channels'][channel]['transducer']
        q['sensitivity'] = float(sensitivity)
        q['unit'] = self.__check_string(unit)
        q['serialNumber'] = self.__check_string(serialNumber)
        q['type']['number'] = self.__check_string(transducerType)
    
    def set_name(self,name_str):
        """Set the name of the next recording.
        
        Parameters:
            name_str (str): Label for the next recording
        """
        
        self.settings['name'] = self.__check_string(name_str)
