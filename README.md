BeautifulDiscord
================

Simple Python script that adds CSS (w/ hot-reload) and JS injection to Discord.

![demo gif](http://i.imgur.com/xq4HS5f.gif)

## Installation

Assuming you have python3 installed, run the following command to fetch the 
code from GitHub and install it on your system. If you use Windows, you may 
have to call python through `python` instead of `python3`.

```
$ python3 -m pip install -U https://github.com/HoLLy-HaCKeR/BeautifulDiscord/archive/master.zip
```

Then, just invoke the script when installed. If you don't pass the `--css`/`--js` 
flag, the css/js files will be placed wherever the Discord app resources are 
found, which is not a very convenient location.

```
$ beautifuldiscord --css C:\mystuff\myown.css --js C:\mystuff\myown.js
```

**NOTE:** Discord has to be running for this to work in first place.
The script works by scanning the active processes and looking for the Discord ones.

## Uninstalling

Pass the `--revert` flag to restore Discord to its initial state. You can also do this manually if your Discord
install gets screwed up, by first locating where Discord stores its resources:

- On Windows, it's `C:\Users\<username>\AppData\Roaming\discord[ptb,canary]\<version>\modules\discord_desktop_core`
- On OSX, it's `~/Library/Application Support/discord[ptb,canary]/<version>/modules/discord_desktop_core`
- On Linux, it's `~/.config/discord[ptb,canary]/<version>/modules/discord_desktop_core`

(`<...>` means it's required, `[...]` means it's optional)

In that folder, there should be four files, with `core.asar` and `original_core.asar` being the interesting ones.
You should then remove the existing `core.asar` and rename `original_core.asar` to `core.asar`.

```
$ beautifuldiscord --revert
```

You can also run it as a package - i.e. `python3 -m beautifuldiscord` - if somehow you cannot
install it as a script that you can run from anywhere.

Afterwards, you can completely uninstall the discord package too:

```
python3 -m pip uninstall beautifuldiscord
```

## Requirements

- Python 3.x (no interest in compatibility with 2.x, untested on Python 3.x versions below 3.4)
- `psutil` library: https://github.com/giampaolo/psutil

Normally, `pip` should install any required dependencies.

## More GIFs

![demo gif](http://i.imgur.com/w0bQOJ6.gif)
