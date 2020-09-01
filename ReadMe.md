# PyBnK : Using Python to communicate with a Brüel &amp; Kjær Type 3050-B-6

To communicate with a stand-alone [Brüel & Kjær Type 3050-B-6](https://www.bksv.com/en/products/data-acquisition-systems-and-hardware/LAN-XI-data-acquisition-hardware/modules/type-3050), it is necessary to have a [Notar™ BZ-7848-A (LAN-XI stand-alone recorder license)](https://www.bksv.com/en/products/data-acquisition-systems-and-hardware/general-purpose-analyzer-system/lan-xi-notar), which allows you to interact with the device via a browser, utilising the Ethernet port at the back of the device. For brevity, in what follows, we will denote the Brüel & Kjær Type 3050-B-6 with a Notar™ BZ-7848-A (LAN-XI stand-alone recorder license) simply as __BnK__.
The browser feature allows for easy access from a network connected device, however there are times when a more automated data collection method is desireable, either because a series of repeatable measurements are being taken or because control of the BnK device is from a device without a user-interface style of browser.

This Python 3 module allows automated interaction with a BnK from any device which can run python 3, such as a Beaglebone Black, Raspberry Pi, or a computer running JupyterLab.
This module has been developed to work with a BnK device running firmware version 2.0.0.214. 
The behaviour for this module for other firmware versions or other models of Brüel & Kjær acquisition system are unknown.

The various specifications for the BnK are contained in the [Brüel & Kjær Type 3050-B-6 brochure](https://www.bksv.com/media/doc/bp2215.pdf).

## Installation

* Clone [PyBnK](https://github.com/uwasystemhealth/PyBnK)
* cd into the PyBnK directory
* Install the package:

```
pip install .
```

You will need to install pysoundfile, if you don't already have it installed:

```
conda install -c conda-forge pysoundfile -y
```

## Getting Started

For an introduction into using this module, please read the [GettingStarted notebook](GettingStarted.ipynb).

As an example, the code below imports the module, loads a device and records 10 seconds of data from a single channel at 8192 SPS, with a 7 Hz high-pass filter.

```
from bnk.bnk import WavHeader, OpenWav, Instrument
bnk_ip = "192.168.0.70"
ADAC = Instrument(bnk_ip)
ADAC.disable_all()
ADAC.set_samplerate(8192)
ADAC.set_name('Test Recording')
ADAC.set_channel(channel=1, name='Input signal', 
                 c_filter='7.0 Hz', c_range='10 Vpeak')
ADAC.powerup()
ADAC.record(10)
ADAC.powerdown()
WAV_file = ADAC.get_wav(directory='samples',recording_id=recording_id)
ADAC.delete_recording(recording_id=recording_id)
wav_data, metadata = OpenWav(WAV_file, verbose=True)
```

## Reference

For a reference guide to the various methods associated with the PyBnK `Instrument` Class and the functions `WavHeader` and `OpenWav`, take a look at the [PyBnK notebook](PyBnK.ipynb).

## Uninstalling

```
pip uninstall PyBnk -y
```

## Contributing

Bugs can be reported at [PyBnK](https://github.com/uwasystemhealth/PyBnK). 

## License

MIT License

Copyright (c) 2019 Ben Travaglione

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
