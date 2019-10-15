#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import shutil

from .utils import try_load_json_file, json, LOGGER
from .constants import CONF_KEY_BASE, CONF_KEY_PLAYERSETTINGS, \
        CONF_KEY_MUSICPROVIDERS, CONF_KEY_PLAYERPROVIDERS, EVENT_CONFIG_CHANGED

class WatchedDict(dict):

    def __init__(self, mass, parent, savefunc, existing_dict=None):
        self.mass = mass
        self.parent = parent
        self.savefunc = savefunc
        if existing_dict:
            for key, value in existing_dict.items():
                self[key] = value
    
    def __setitem__(self, key, new_value):
        # optional processing here
        if key not in self:
            if isinstance(new_value, dict):
                new_value = WatchedDict(self.mass, key, self.savefunc, new_value)
            super().__setitem__(key, new_value)
        elif self[key] != new_value:
            # value changed
            super().__setitem__(key, new_value)
            self[key] = new_value
            self.mass.event_loop.create_task(
                    self.mass.signal_event(EVENT_CONFIG_CHANGED, f"{self.parent}.{key}"))
            self.savefunc()

class MassConfig(WatchedDict):
    ''' Class which holds our configuration '''

    def __init__(self, mass):
        self.mass = mass
        self.loading = False
        self.savefunc = self.__save
        self.parent = None
        self[CONF_KEY_BASE] = WatchedDict(mass, None, self.__save)
        self[CONF_KEY_MUSICPROVIDERS] = WatchedDict(mass, None, self.__save)
        self[CONF_KEY_PLAYERPROVIDERS] = WatchedDict(mass, None, self.__save)
        self[CONF_KEY_PLAYERSETTINGS] = WatchedDict(mass, None, self.__save)
        self.__load()

    @property
    def base(self):
        ''' return base config '''
        return self[CONF_KEY_BASE]

    @property
    def players(self):
        ''' return player settings '''
        return self[CONF_KEY_PLAYERSETTINGS]

    @property
    def playerproviders(self):
        ''' return playerprovider settings '''
        return self[CONF_KEY_PLAYERPROVIDERS]

    @property
    def musicproviders(self):
        ''' return musicprovider settings '''
        return self[CONF_KEY_MUSICPROVIDERS]

    def create_module_config(self, conf_key, conf_entries, base_key=CONF_KEY_BASE):
        ''' create (or update) module configuration '''
        cur_conf = self[base_key].get(conf_key)
        new_conf = {}
        for key, def_value, desc in conf_entries:
            if not cur_conf or not key in cur_conf:
                new_conf[key] = def_value
            else:
                new_conf[key] = cur_conf[key]
        new_conf['__desc__'] = conf_entries
        self[base_key][conf_key] = new_conf
        return self[base_key][conf_key]

    def __save(self):
        ''' save config to file '''
        if self.loading:
            LOGGER.warning("save already running")
            return
        self.loading = True
        # backup existing file
        conf_file = os.path.join(self.mass.datapath, 'config.json')
        conf_file_backup = os.path.join(self.mass.datapath, 'config.json.backup')
        if os.path.isfile(conf_file):
            shutil.move(conf_file, conf_file_backup)
        # remove description keys from config
        final_conf = {}
        for key, value in self.items():
            final_conf[key] = {}
            for subkey, subvalue in value.items():
                if subkey != "__desc__":
                    final_conf[key][subkey] = subvalue
        with open(conf_file, 'w') as f:
            f.write(json.dumps(final_conf, indent=4))
        self.loading = False
        
    def __load(self):
        '''load config from file'''
        self.loading = True
        conf_file = os.path.join(self.mass.datapath, 'config.json')
        data = try_load_json_file(conf_file)
        if not data:
            # might be a corrupt config file, retry with backup file
            conf_file_backup = os.path.join(self.mass.datapath, 'config.json.backup')
            data = try_load_json_file(conf_file_backup)
        if data:
            for key, value in data.items():
                self[key] = value
        self.loading = False