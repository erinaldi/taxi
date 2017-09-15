#!/usr/bin/env python2
"""
"""

import os

import taxi.mcmc


## File naming conventions for pure gauge theory
class PureGaugeFnConvention(taxi.mcmc.BasicMCMCFnConvention):
    def write(self, params):
        return "{prefix}_{Ns}_{Nt}_{beta}_{label}_{_traj}".format(prefix=self.prefix, 
                _traj=(params['traj'] if params.has_key('traj') else params['final_traj']), **params)
    
    def read(self, fn):
        words = os.path.basename(fn).split('_')
        assert len(words) == 6
        return {
            'prefix' : words[0],
            'Ns' : int(words[1]), 'Nt' : int(words[2]),
            'beta' : float(words[3]),
            'label' : float(words[5]),
            'traj' : int(words[5])
        }


class PureGaugeSpectroFnConvention(taxi.mcmc.BasicMCMCFnConvention):
    def write(self, params):
        # xspec... for screening, tspec... for time-direction; ...spec for normal APBC spectro, ...specpa for P+A spectro
        prefix = ('x' if params['screening'] else 't') + 'spec' + ('pa' if params['p_plus_a'] else '')
        
        return "{prefix}_{irrep}_r{r0}_{Ns}_{Nt}_{beta}_{kappa}_{label}_{_traj}".format(
                prefix=prefix,
                _traj=(params['traj'] if params.has_key('traj') else params['final_traj']),
                **params)
        
    def read(self, fn):
        words = os.path.basename(fn).split('_')
        assert len(words) == 9
        assert 'spec' in words[0]
        return {
            'file_prefix' : words[0],
            'p_plus_a' : words[0].endswith('pa'),
            'screening' : words[0].startswith('x'),
            'irrep' : words[1],
            'r0' : float(words[2][1:]),
            'Ns' : int(words[3]), 'Nt' : int(words[4]),
            'beta' : float(words[5]),
            'kappa' : float(words[6]),
            'label' : words[7],
            'traj' : int(words[8])
        }
        
        
        
## File naming conventions for the SU(4) 2xF 2xA_2 multirep theory
class MrepFnConvention(taxi.mcmc.BasicMCMCFnConvention):
    def write(self, params):
        # Assume each kappa=0 if not specified
        k4 = params.get('k4', 0)
        k6 = params.get('k6', 0)
        
        return "{prefix}_{Ns}_{Nt}_{beta}_{_k4}_{_k6}_{label}_{_traj}".format(
                prefix=self.prefix, _k4=k4, _k6=k6,
                _traj=(params['traj'] if params.has_key('traj') else params['final_traj']),
                **params)
    
    def read(self, fn):
        words = os.path.basename(fn).split('_')
        assert len(words) == 8
        return {
            'file_prefix' : words[0],
            'Ns' : int(words[1]), 'Nt' : int(words[2]),
            'beta' : float(words[3]),
            'k4' : float(words[4]),
            'k6' : float(words[5]),
            'label' : words[6],
            'traj' : int(words[7])
        }
        
        
class MrepSpectroFnConvention(taxi.mcmc.BasicMCMCFnConvention):
    def write(self, params):
        # xspec... for screening, tspec... for time-direction; ...spec for normal APBC spectro, ...specpa for P+A spectro
        prefix = ('x' if params['screening'] else 't') + 'spec' + ('pa' if params['p_plus_a'] else '')
        
        # Assume each kappa=0 if not specified
        k4 = params.get('k4', 0)
        k6 = params.get('k6', 0)
        
        return "{prefix}_{irrep}_r{r0}_{Ns}_{Nt}_{beta}_{_k4}_{_k6}_{label}_{_traj}".format(
                prefix=prefix, _k4=k4, _k6=k6,
                _traj=(params['traj'] if params.has_key('traj') else params['final_traj']),
                **params)
        
    def read(self, fn):
        words = os.path.basename(fn).split('_')
        assert len(words) == 10
        assert 'spec' in words[0]
        return {
            'file_prefix' : words[0],
            'p_plus_a' : words[0].endswith('pa'),
            'screening' : words[0].startswith('x'),
            'irrep' : words[1],
            'r0' : float(words[2][1:]),
            'Ns' : int(words[3]), 'Nt' : int(words[4]),
            'beta' : float(words[5]),
            'k4' : float(words[6]), 'k6' : float(words[7]),
            'label' : words[8],
            'traj' : int(words[9])
        }
        