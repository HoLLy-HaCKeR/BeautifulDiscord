#!/usr/bin/env python

import os
import shutil
import argparse
import textwrap
import subprocess
import psutil
import sys
from beautifuldiscord.asar import Asar

class DiscordProcess:
    def __init__(self, path, exe):
        self.path = path
        self.exe = exe
        self.processes = []

    def terminate(self):
        for process in self.processes:
            # terrible
            process.kill()

    def launch(self):
        with open(os.devnull, 'w') as f:
            subprocess.Popen([os.path.join(self.path, self.exe)], stdout=f, stderr=subprocess.STDOUT)

    @property
    def resources_path(self):
        if sys.platform == 'darwin':
            # OS X has a different resources path
            # Application directory is under <[EXE].app/Contents/MacOS/[EXE]>
            # where [EXE] is Discord Canary, Discord PTB, etc
            # Resources directory is under </Applications/[EXE].app/Contents/Resources/app.asar>
            # So we need to fetch the folder based on the executable path.
            # Go two directories up and then go to Resources directory.
            return os.path.abspath(os.path.join(self.path, '..', 'Resources'))
        return os.path.join(self.path, 'resources')

    @property
    def script_path(self):
        if sys.platform == 'win32':
            # On Windows:
            # path is C:\Users\<UserName>\AppData\Local\<Discord>\app-<version>
            # script: C:\Users\<UserName>\AppData\Roaming\<DiscordLower>\<version>\modules\discord_desktop_core
            # don't try this at home
            path = os.path.split(self.path)
            app_version = path[1].replace('app-', '')
            discord_version = os.path.basename(path[0])
            return os.path.expandvars(os.path.join('%AppData%',
                                                   discord_version,
                                                   app_version,
                                                   r'modules\discord_desktop_core'))
        elif sys.platform == 'darwin':
            # macOS doesn't encode the app version in the path, but rather it stores it in the Info.plist
            # which we can find in the root directory e.g. </Applications/[EXE].app/Contents/Info.plist>
            # After we obtain the Info.plist, we parse it for the `CFBundleVersion` key
            # The actual path ends up being in ~/Library/Application Support/<DiscordLower>/<version>/modules/...
            import plistlib as plist
            info = os.path.abspath(os.path.join(self.path, '..', 'Info.plist'))
            with open(info, 'rb') as fp:
                info = plist.load(fp)

            app_version = info['CFBundleVersion']
            discord_version = info['CFBundleName'].replace(' ', '').lower()
            return os.path.expanduser(os.path.join('~/Library/Application Support',
                                                  discord_version,
                                                  app_version,
                                                  'modules/discord_desktop_core'))
        else:
            # Discord is available typically on /opt/discord-canary directory
            # The modules are under ~/.config/discordcanary/0.0.xx/modules/discord_desktop_core
            # To get the version number we have to iterate over ~/.config/discordcanary and find the
            # folder with the highest version number
            discord_version = os.path.basename(self.path).replace('-', '')
            config = os.path.expanduser(os.path.join('~/.config', discord_version))

            versions_found = {}
            for subdirectory in os.listdir(config):
                if not os.path.isdir(os.path.join(config, subdirectory)):
                    continue

                try:
                    # versions are A.B.C
                    version_info = tuple(int(x) for x in subdirectory.split('.'))
                except Exception as e:
                    # shucks
                    continue
                else:
                    versions_found[subdirectory] = version_info

            if len(versions_found) == 0:
                raise RuntimeError('Could not find discord application version under "{}".'.format(config))

            app_version = max(versions_found.items(), key=lambda t: t[1])
            return os.path.join(config, app_version[0], 'modules', 'discord_desktop_core')

    @property
    def script_file(self):
        return os.path.join(self.script_path, 'core', 'app', 'mainScreen.js')

def extract_asar():
    try:
        with Asar.open('./core.asar') as a:
            try:
                a.extract('./core')
            except FileExistsError:
                answer = input('asar already extracted, overwrite? (Y/n): ')

                if answer.lower().startswith('n'):
                    print('Exiting.')
                    return False

                shutil.rmtree('./core')
                a.extract('./core')

        shutil.move('./core.asar', './original_core.asar')
    except FileNotFoundError as e:
        print('WARNING: app.asar not found')

    return True

def repack_asar():
    try:
        with Asar.from_path('./core') as a:
            with open('./core.asar', 'wb') as fp:
                a.fp.seek(0)
                fp.write(a.fp.read())
        shutil.rmtree('./core')
    except Exception as e:
        print('ERROR: {0.__class__.__name__} {0}'.format(e))

def parse_args():
    description = """\
Unpacks Discord and adds CSS/JavaScript hot-reloading.

Discord has to be open for this to work. When this tool is ran,
Discord will close and then be relaunched when the tool completes.
CSS files must have the ".css" extension, and JavaScript files must
have the ".js" extension.
"""
    parser = argparse.ArgumentParser(description=description.strip())
    parser.add_argument('--css', metavar='file_or_dir', help='Location of the CSS file or directory to watch')
    parser.add_argument('--js', metavar='file_or_dir', help='Location of the JavaScript file or directory to watch')
    parser.add_argument('--revert', action='store_true', help='Reverts any changes made to Discord (does not delete CSS)')
    args = parser.parse_args()
    return args

def discord_process():
    executables = {}
    for proc in psutil.process_iter():
        try:
            (path, exe) = os.path.split(proc.exe())
        except (psutil.Error, OSError):
            pass
        else:
            if exe.startswith('Discord') and not exe.endswith('Helper'):
                entry = executables.get(exe)

                if entry is None:
                    entry = executables[exe] = DiscordProcess(path=path, exe=exe)

                entry.processes.append(proc)

    if len(executables) == 0:
        raise RuntimeError('Could not find Discord executable.')

    if len(executables) == 1:
        r = executables.popitem()
        print('Found {0.exe} under {0.path}'.format(r[1]))
        return r[1]

    lookup = list(executables)
    for index, exe in enumerate(lookup):
        print('%s: Found %s' % (index, exe))

    while True:
        index = input("Discord executable to use (number): ")
        try:
            index = int(index)
        except ValueError as e:
            print('Invalid index passed')
        else:
            if index >= len(lookup) or index < 0:
                print('Index too big (or small)')
            else:
                key = lookup[index]
                return executables[key]

def revert_changes(discord):
    try:
        shutil.move('./original_core.asar', './core.asar')
        shutil.move('./original_index.js', './index.js')
    except FileNotFoundError as e:
        print('No changes to revert.')
    else:
        print('Reverted changes, no more CSS hot-reload :(')

    discord.launch()

def remove_csp():
	shutil.move('./index.js', './original_index.js')

	no_csp_script = textwrap.dedent("""\
		require("electron").session.defaultSession.webRequest.onHeadersReceived(function(details, callback) {
			const responseHeaders = {};
			for (let header in details.responseHeaders) {
				if (!header.match(/^content-security/i)) {
					responseHeaders[header] = details.responseHeaders[header]
				}
			} callback({
				cancel: false,
				responseHeaders
			});
		});

		module.exports = require('./core.asar');""")
	
	with open('./index.js', 'w', encoding='utf-8') as f:
		f.write(no_csp_script)

def main():
    args = parse_args()
    try:
        discord = discord_process()
    except Exception as e:
        print(str(e))
        return

    if args.css:
        args.css = os.path.abspath(args.css)
    else:
        args.css = os.path.join(discord.script_path, 'discord-custom.css')
    if args.js:
        args.js = os.path.abspath(args.js)
    else:
        args.js = os.path.join(discord.script_path, 'discord-custom.js')

    os.chdir(discord.script_path)

    args.css = os.path.abspath(args.css)
    args.js = os.path.abspath(args.js)

    discord.terminate()

    if args.revert:
        return revert_changes(discord)

    if not os.path.exists(args.css):
        with open(args.css, 'w', encoding='utf-8') as f:
            f.write('/* put your custom css here. */\n')
    if not os.path.exists(args.js):
        with open(args.js, 'w', encoding='utf-8') as f:
            f.write('// put your custom js here.\n')

    if not extract_asar():
        discord.launch()
        return

    injection_script = textwrap.dedent("""\
        window._fs = require("fs");
        window._path = require("path");
        window._fileWatcherCSS = null;
        window._fileWatcherJS = null;
        window._styleTag = {};
        window._scriptTag = {};

        window.applyCSS = function(path, name) { window._apply(path, name, "CSS"); };
        window.applyJS =  function(path, name) { window._apply(path, name, "JS");  };

        window._apply = function(path, name, type) {
            var elementType = type == "CSS" ? "style" : "script";
            var tag = type == "CSS" ? window._styleTag : window._scriptTag;
            var customContent = window._fs.readFileSync(path, "utf-8");
            if (!tag.hasOwnProperty(name)) {
                tag[name] = document.createElement(elementType);
                document.head.appendChild(tag[name]);
            }
            tag[name].innerHTML = customContent;
        }

        window.clearCSS = function(name) { window._clear(name, "CSS"); };
        window.clearJS =  function(name) { window._clear(name, "JS");  };

        window._clear = function(name) {
            var tag = type == "CSS" ? window._styleTag : window._scriptTag;
            if (tag.hasOwnProperty(name)) {
                tag[name].innerHTML = "";
                tag[name].parentElement.removeChild(tag[name]);
                delete tag[name];
            }
        }

        window.watchCSS = function(path) { window.watch(path, "CSS"); };
        window.watchJS  = function(path) { window.watch(path, "JS");  };

        window.watch = function(path, type) {
            var ext = '.' + type.toLowerCase();
            var fnApply = window["apply" + type];
            var fnClear = window["clear" + type];
            var watcher = window["_fileWatcher" + type];

            if (window._fs.lstatSync(path).isDirectory()) {
                files = window._fs.readdirSync(path);
                dirname = path;
            } else {
                files = [window._path.basename(path)];
                dirname = window._path.dirname(path);
            }

            for (var i = 0; i < files.length; i++) {
                var file = files[i];
                if (file.endsWith(ext)) {
                    fnApply(window._path.join(dirname, file), file)
                }
            }

            if(watcher === null) {
                watcher = window._fs.watch(path, { encoding: "utf-8" },
                    function(eventType, filename) {
                        if (!filename.endsWith(ext)) return;
                        path = window._path.join(dirname, filename);
                        if (eventType === "rename" && !window._fs.existsSync(path)) {
                            fnClear(filename);
                        } else {
                            fnApply(window._path.join(dirname, filename), filename);
                        }
                    });
            }
        };

        window.tearDownCSS = function() { window.tearDown("CSS"); };
        window.tearDownJS  = function() { window.tearDown("JS");  };

        window.tearDown = function(type) {
            var watcher = window["_fileWatcher" + type];
            var tag = type == "CSS" ? window._styleTag : window._scriptTag;
            var fnClear = window["clear" + type];
            for (var key in tag) {
                if (tag.hasOwnProperty(key)) {
                    fnClear(key);
                }
            }
            if(watcher !== null) { watcher.close(); watcher = null; }
        };
        
	window.removeDuplicateCSS = function(){
        	const styles = [...document.getElementsByTagName("style")];
        	const styleTags = window._styleTag;
        
        	for(let key in styleTags){
        		for (var i = 0; i < styles.length; i++) {
        			const keyStyle = styleTags[key];
        			const curStyle = styles[i];
        
        			if(curStyle !== keyStyle) {
        				const compare	 = keyStyle.innerText.localeCompare(curStyle.innerText);
        
        				if(compare === 0){
        					const parent = curStyle.parentElement;
        					parent.removeChild(curStyle);
        				}
        			}
        		}
        	}
        };
	
	
        window.applyAndWatchCSS = function(path) { window.applyAndWatch(path, "CSS"); };
        window.applyAndWatchJS  = function(path) { window.applyAndWatch(path, "JS");  };

        window.applyAndWatch = function(path, type) {
            window.tearDown(type);
            window.watch(path, type);
        };

        window.applyAndWatchCSS('%s');
        window.applyAndWatchJS('%s');
	 window.removeDuplicateCSS(%s);
    """ % (args.css.replace('\\', '\\\\'), args.js.replace('\\', '\\\\')))


    injection_path = os.path.expanduser(os.path.join('~', '.beautifuldiscord'))
    if not os.path.exists(injection_path):
        os.mkdir(injection_path)

    injection_file = os.path.abspath(os.path.join(injection_path, 'injection.js'))
    with open(injection_file, 'w', encoding='utf-8') as f:
        f.write(injection_script)

    reload_script = textwrap.dedent("""\
        mainWindow.webContents.on('dom-ready', function () {
          var _fs = require('fs');
          mainWindow.webContents.executeJavaScript(
            _fs.readFileSync('%s', 'utf-8')
          );
        });
    """ % injection_file.replace('\\', '\\\\'))

    with open(discord.script_file, 'rb') as f:
        entire_thing = f.read()

    index = entire_thing.index(b"mainWindow.on('blur'")

    if index == -1:
        # failed replace for some reason?
        print('warning: nothing was done.\n' \
              'note: blur event was not found for the injection point.')
        revert_changes(discord)
        discord.launch()
        return

    # yikes
    to_write = entire_thing[:index] + reload_script.encode('utf-8') + entire_thing[index:]
    to_write = to_write.replace(b'nodeIntegration: false', b'nodeIntegration: true', 1)

    with open(discord.script_file, 'wb') as f:
        f.write(to_write)

    # repack the asar so discord stops complaining
    repack_asar()

    # finally, remove csp by injecting into index.js
    remove_csp()

    print(
        '\nDone!\n' +
        '\nYou may now edit your %s file (CSS),' % os.path.abspath(args.css) +
        'or %s file (JS),\n' % os.path.abspath(args.js) +
        "which will be reloaded whenever it's saved.\n" +
        '\nRelaunching Discord now...'
    )

    discord.launch()


if __name__ == '__main__':
    main()
