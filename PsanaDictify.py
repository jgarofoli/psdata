# import standard python system tools
#import argparse
#from glob import glob
import re
import operator
#import sys
#import os
#import imp
#import subprocess
#import inspect
import pprint
import time

class PsanaDictify(object):
    """Tab accessible dictified data from psana keys.
       e.g., 
            evt = PsanaDictify(ds.events().next())
            configStore = PsanaDictify(ds.env().configStore())
    """

    _init_attrs = ['get','put','keys']
    _det_dicts = {}

    def __init__(self, dat):
        for attr in self._init_attrs:
            setattr(self, attr, getattr(dat,attr))

        self.build_keys_dict()

        for attr in self._keys_dict:
            self._det_dicts[attr] = DetDictify(self._keys_dict, attr)

    def __getattr__(self, attr):
        if attr in self._alias_dict:
            attr = self._alias_dict[attr]
        if attr in self._keys_dict:
            return self._det_dicts[attr]

    def __dir__(self):
        all_attrs = set(self._alias_dict.keys() + 
                        self.__dict__.keys() + dir(PsanaDictify))
           
        return list(sorted(all_attrs))


    def build_keys_dict(self):
        """Builds self._keys_dict dictionary from psana keys.
           Builds self._alias_dict dictionary of aliases based on info in psana keys.
        """
        keys_dict = {}
        alias_dict = {}
        for evt_key in self.keys():
            key_dict = {}
            if hasattr(evt_key,'src'):
                src = evt_key.src()
            else:
                src = evt_key
            if hasattr(src,'detName'):
                if src.detName() in ['NoDetector']:
                    det_key = '_'.join([src.devName(),str(src.devId())])
                else:
                    det_key = '_'.join([src.detName(),str(src.detId()),
                                        src.devName(),str(src.devId())])
                src_attrs = ['detName','detId','devName','devId']
            elif hasattr(src,'typeName'):
                det_key = '_'.join([src.typeName(),str(src.type())])
                src_attrs = ['typeName']
            else:
                src_attrs = None
                det_key = None

            if src_attrs:
                for attr in src_attrs:
                    key_dict[attr] = getattr(src,attr)()

            if hasattr(evt_key,'alias'):
                key_dict['alias'] = evt_key.alias()

            if hasattr(evt_key,'type') and evt_key.type():
# Put the event object with attributes into a dictionary 
# in order to better handle evaluating the functions 
# as properties and to keep the functions in order
# to extract the relevant part of the doc string as
# a description and units.
                evt_funcs = self.get(evt_key.type(), 
                                     evt_key.src(), 
                                     evt_key.key())
                key_dict['attrs'] = {}
                for attr in dir(evt_key.type()):
                    if not attr.startswith(('_','TypeId','Version')):
                        key_dict['attrs'][attr] = getattr(evt_funcs, attr)

#                key_dict['attrs'] = {attr: getattr(evt_funcs, attr) for attr
#                                     in dir(evt_key.type())
#                                     if not attr.startswith(('_','TypeId','Version'))}:

                psana_module = evt_key.type().__module__
                module = psana_module.lstrip('psana.')
        #        module = psana_module.replace('psana.','')
                psana_class = evt_key.type().__name__
                if not module:
                    device = psana_class
                    if not det_key:
                        det_key = psana_class

                else:
                    if module == 'Bld':
                        device = psana_class.strip('BldData')

                    elif module == 'Lusi':
                        device = psana_class.strip('Fex')
                    else:
                        device = module

        ## strip of Version Number           
                    if re.search(r"V.?\b", device):
                         device = device[:-2]

                    if not det_key:
                        det_key = '_'.join([module,psana_class])

        # Bld data do not yet have aliases -- ask daq group to add consistent ones.
                    if module == 'Bld':
                        if 'alias' not in key_dict or not key_dict['alias']:
                            if det_key[-2] in '_':
                                key_dict['alias'] = det_key[:-2]
                            else:
                                key_dict['alias'] = det_key

                if psana_class == 'EventId':
                    key_dict['alias'] = psana_class
                    key_dict['TypeId'] = 0
                    key_dict['Version'] = 0
                else:
                    key_dict['TypeId'] = evt_key.type().TypeId
                    key_dict['Version'] = evt_key.type().Version

                key_dict['psana_module'] = psana_module
                key_dict['psana_class'] = psana_class
                key_dict['device'] = device
                type_key = '_'.join([key_dict['device'],
                                     str(key_dict['TypeId']),
                                     str(key_dict['Version'])])
                
                det_key = det_key.replace('-','_')
                key_dict['det_key'] = det_key
                key_dict['evt_key'] = evt_key
                key_dict['type_key'] = type_key
                if 'alias' not in key_dict:
                    key_dict['alias'] = det_key
                
                if det_key not in keys_dict:
                    keys_dict[det_key] = {}
                    alias_dict[key_dict['alias']] = det_key

                keys_dict[det_key][device] = key_dict

        self._keys_dict = keys_dict
        self._alias_dict = alias_dict


class DetDictify(object):
    """Dictify the detectors with types.
    """
    def __init__(self, keys_dict, det, show_attrs=True):
        self._det = det
        self._keys = keys_dict[det]
        if show_attrs:
            self._attr_type = {attr: typ for typ, item in self._keys.items() 
                                for attr in item['attrs'].keys()}
        else:
            self._attr_type = {}

        self._types = {typ: TypeDictify(keys_dict, det, typ) for typ in keys_dict[det].keys()}

    def show_info(self):
        for typ in self._types:
            getattr(getattr(self,typ),'show_info')()

    def __repr__(self):
        repr_str = '< {:} {:}>'.format(self._det, self.__class__.__name__)
        self.show_info()
        return repr_str

    def __getattr__(self, attr):
        if attr in self._types.keys():
            return self._types[attr]
        elif attr in self._attr_type.keys():
            type = self._attr_type[attr]
            return self._types[attr].get_attr(attr)

    def __dir__(self):
        all_attrs = set(self._types.keys() + 
                        self._attr_type.keys() +
                        self.__dict__.keys() + dir(DetDictify))
           
        return list(sorted(all_attrs))

class TypeDictify(object):
    
    def __init__(self, keys_dict, det, typ):
        self._det = det
        self._typ = typ
        self._attrs = keys_dict[det][typ]['attrs'] 
        self._show_attrs = self._attrs.keys()

    def get_attr(self, attr):
        if attr in self._attrs:
            value = self._attrs[attr]        
            try:
                value = value()
            except:
                pass
            if hasattr(value,'__func__'):
                try:
                    value = value()
                except:
                    pass
        else:
            value = None
            
        if isinstance(value, list):
            try:
                value = [val() for val in value]
            except:
                if len(value) < 100:
                    for i, val in enumerate(value):
                        try:
                            val = val()
                        except:
                            pass
                        setattr(self, '{:}{:02}'.format(attr,i), ReDictify(val))

        return value

    def show_info(self, attrs=None):
        print '-'*80
        print self._det, self._typ
        print '-'*80
        if not attrs:
            attrs = list(sorted(self._show_attrs))
        for attr in attrs:
            item = self._attrs[attr]
            print func_repr(attr, self._attrs[attr]) 

    def __repr__(self):
        repr_str = '< {:} {:} {:}>'.format(self._det, self._typ, self.__class__.__name__) 
        self.show_info()
        return repr_str

    def __getattr__(self, attr):
        if attr in self._attrs:
            return self.get_attr(attr)

    def __dir__(self):
        all_attrs = set(self._attrs.keys() + 
                        self.__dict__.keys() + dir(TypeDictify))
           
        return list(sorted(all_attrs))

class ReDictify(object):

    def __init__(self, obj):
        self._attrs = [attr for attr in dir(obj) if not attr.startswith('_')]
        for attr in self._attrs:
            value = getattr(obj, attr)
            try:
                value = value()
            except:
                pass

            setattr(self, attr, value)

    def show_info(self, attrs=None):
        if not attrs:
            attrs = list(sorted(self._attrs))
        for attr in attrs:
            value = getattr(self,attr)
            print func_repr(attr, value)

    def __repr__(self):
        repr_str = '< {:}>'.format(self.__class__.__name__) 
        self.show_info()
        return repr_str


def get_unit_from_doc(doc):
    try:
        unit = '{:}'.format(doc.rsplit(' in ')[-1])
        unit = unit.rstrip('.').rstrip(',').rsplit(' ')[0].rstrip('.').rstrip(',')
    except:
        unit = None
    return unit

def func_dict(attr, func):
    fdict = {'attr': attr,
             'doc': '',
             'unit': '',
             'str':  'NA',
             'func': func}

    value = func
    try:
        value = value()
    except:
        pass

    if isinstance(value,str):
        fdict['str'] = value
    else:
        if hasattr(value,'mean'):
            fdict['str'] = '<{:.4}>'.format(value.mean())
        else:
            try:
                doc = func.__doc__.split('\n')[-1].lstrip(' ')
                fdict['doc'] = doc
                fdict['str'] = '{:10.5g}'.format(value)
                fdict['unit'] = get_unit_from_doc(doc)
            except:
                try:
                    fdict['str'] = value.__str__()
                except:
                    pass

    fdict['value'] = value

    return fdict

def func_repr(attr, func):
    fdict = func_dict(attr, func)

    return '{attr:18s} {str:>10} {unit:6} {doc:}'.format(**fdict)



class EpicsDictify(object):

    def __init__(self, epicsStore):
        """Show epics PVs with tabs.
        """

        pv_dict = {}
        for pv in  epicsStore.names():
            name = re.sub(':|\.','_',pv)
            #check if valid -- some old data had aliases generated from comments in epicsArch files.
            if re.match("[_A-Za-z][_a-zA-Z0-9]*$", name):
                func = epicsStore.getPV(pv)
                pvname = epicsStore.pvName(pv)
                if pvname:
                    pvalias = pv
                else:
                    pvalias = epicsStore.alias(pv)
                    pvname = pv

                components = re.split(':|\.|_',pv)
                for i,item in enumerate(components):
                    if item[0].isdigit():
                         components[i] = 'n'+components[i]

                pv_dict[name] =  { 'pv': pvname,
                                   'alias': pvalias,
                                   'components': components,
                                   'func': func}

        self._pv_dict = pv_dict

    def epics(self):
        return PVdictify(self._pv_dict)

class PVdictify(object):
    """Dot.dictifies a dictionary of {PVnames: values}.
    """
#    _levels = ['location','region','component','number','field']

    def __init__(self,attr_dict,level=0):
        self._attr_dict = attr_dict
        self._level = int(level)
        self._attrs = list(set([pdict['components'][level]
                                for key,pdict in attr_dict.items()]))

    def show_info(self):
        """Show information from PVdictionary for all PV's starting with 
           the specified dictified base.
           (i.e. ':' replaced by '.' to make them tab accessible in python)
        """
        print self.get_info()

    def get_info(self):
        """Return string representation of all PV's starting with 
           the specified dictified base.
           (i.e. ':' replaced by '.' to make them tab accessible in python)
        """
        info = ''
#        for key,pdict in self._attr_dict.items():
        items = sorted(self._attr_dict.items(), key=operator.itemgetter(0))
        for key,pdict in items:
            alias = pdict['alias']
            if alias:
                name = alias
                pv = pdict['pv']
            else:
                name = pdict['pv']
                pv = ''

            value = pdict['func'].value(0)
            try:
                info += '{:30s} {:10.4g} -- {:30s}\n'.format(name,value,pv)
            except:
                info += '{:30s} {:>10} -- {:30s}\n'.format(name,value,pv)
        return info


class PVdictify(object):
    """Dot.dictifies a dictionary of {PVnames: values}.
    """
#    _levels = ['location','region','component','number','field']

    def __init__(self,attr_dict,level=0):
        self._attr_dict = attr_dict
        self._level = int(level)
        self._attrs = list(set([pdict['components'][level]
                                for key,pdict in attr_dict.items()]))

    def show_info(self):
        """Show information from PVdictionary for all PV's starting with 
           the specified dictified base.
           (i.e. ':' replaced by '.' to make them tab accessible in python)
        """
        print self.get_info()

    def get_info(self):
        """Return string representation of all PV's starting with 
           the specified dictified base.
           (i.e. ':' replaced by '.' to make them tab accessible in python)
        """
        info = ''
#        for key,pdict in self._attr_dict.items():
        items = sorted(self._attr_dict.items(), key=operator.itemgetter(0))
        for key,pdict in items:
            alias = pdict['alias']
            if alias:
                name = alias
                pv = pdict['pv']
            else:
                name = pdict['pv']
                pv = ''

            value = pdict['func'].value(0)
            try:
                info += '{:30s} {:10.4g} -- {:30s}\n'.format(name,value,pv)
            except:
                info += '{:30s} {:>10} -- {:30s}\n'.format(name,value,pv)
        return info

    def __getattr__(self,attr):
        if attr in self._attrs:
            attr_dict = {key: pdict for key,pdict in self._attr_dict.items()
                         if pdict['components'][self._level] in attr}
            if len(attr_dict) == 1:
                key = attr_dict.keys()[0]
                if len(self._attr_dict[key]['components']) == (self._level+1):
                    pvdata = self._attr_dict[key]['func']
                    if pvdata.isCtrl():
                        val = None
                        print 'Warning: {pv} pv is ctrl'.format(pv=pv)
                    else:
                        val = pvdata.value(0)
                    return val
            if len(attr_dict) > 0:
                return PVdictify(attr_dict,level=self._level+1)

    def __repr__(self):
        return self.get_info()

    def __dir__(self):
        all_attrs = set(self._attrs +
                        self.__dict__.keys() + dir(PVdictify))
        return list(sorted(all_attrs))





