import os


### Job classes
class Job(object):
    def __init__(self, req_time=0, **kwargs):
        self.req_time = req_time
        self.status = 'pending'
        
        # Tree properties
        self.trunk = False
        self.branch_root = False
        
        # Want a default, but don't clobber anything set by a subclass before calling superconstructor
        if not hasattr(self, 'depends_on'):
            self.depends_on = []
        
    def compile(self):
        # Package in to JSON forest format
        self.compiled = {
            'id'        : self.job_id,
            'req_time'  : self.req_time,
            'status'    : self.status,
        }
        
        # Get dependencies in job_id format
        if not hasattr(self, 'depends_on') or self.depends_on is None or len(self.depends_on) == 0:
            self.compiled['depends_on'] = None
        else:
            self.compiled['depends_on'] = [d.job_id for d in self.depends_on]

    def count_unresolved_dependencies(self, task_blob):
        """Looks at the status of all jobs in the job forest DB that 'task' depends upon.
        Counts up number of jobs that are not complete, and number of jobs that are failed.
        Returns tuple (n_unresolved, n_failed)"""
        
        dependencies = self.depends_on
        
        # Sensible behavior for dependency-tree roots
        if dependencies is []:
            return 0, 0
        
        # Count up number of incomplete, number of failed
        N_unresolved = 0
        N_failed = 0
        for dep_job in dependencies:
            dependency_id = dep_job.job_id
            if not task_blob.has_key(dependency_id):
                continue # Completes weren't requested in task blob
            dependency_status = task_blob[dependency_id]['status']
            if dependency_status != 'complete':
                N_unresolved += 1
            if dependency_status == 'failed':
                N_failed += 1

        return N_unresolved, N_failed

class CopyJob(Job):
    def __init__(self, src, dest, req_time=60, **kwargs):
        super(CopyJob, self).__init__(req_time=req_time, **kwargs)
        
        self.src = src
        self.dest = dest
        
        
    def compile(self):
        super(CopyJob, self).compile()
        
        self.compiled.update({
                'task_type' : 'copy',
                'task_args' : {
                    'src' : self.src,
                    'dest' : self.dest
                }
            })    


class PureGaugeORAJob(Job):
    pg_script = 'pure_gauge_ora.py'
    pg_binary_path = '/path/to/ora/binary'
    
    def __init__(self, Ns, Nt, beta, label, count,
                 req_time,
                 N_traj, nsteps, qhb_steps,
                 starter, seed,
                 warms=0,
                 **kwargs):
        super(PureGaugeORAJob, self).__init__(req_time=req_time, **kwargs)
        
        self.trunk = True # This is a 'trunk' job -- stream forks on these
        
        # Physical parameters
        self.Ns = Ns
        self.Nt = Nt
        self.beta = beta
        
        self.req_time = req_time
        self.count = count
        
        # Stream/ensemble name, filesystem
        self.label = label
        self.generate_ensemble_name()
        self.generate_gaugefilename()
        self.generate_outfilename()
        
        # Deterministically generate a stream seed if none is provided
        self.seed = seed
            
        # Integrator parameters
        self.N_traj = N_traj
        self.nsteps = nsteps
        self.qhb_steps = qhb_steps
        self.warms = warms
                
        # How to start stream
        self.starter = starter
        if isinstance(starter, PureGaugeORAJob) or starter is None:
            pass
        elif isinstance(starter, str):
            assert os.path.exists(starter)
        else:
            raise Exception("Invalid starter {s}".format(s=starter))
            
    def generate_ensemble_name(self):
        self.ensemble_name = "{Ns}_{Nt}_{beta}_{label}".format(Ns=self.Ns, Nt=self.Nt, beta=self.beta, label=self.label)
    def generate_gaugefilename(self):
        self.saveg = "Gauge_" + self.ensemble_name + "_{count}".format(count=self.count)
    def generate_outfilename(self):
        self.fout = "out_" + self.ensemble_name + "_{count}".format(count=self.count)
            
    def compile(self):
        super(PureGaugeORAJob, self).compile()
        
        cmd_line_args = {
            "binary" : self.pg_binary_path,
            "seed"   : self.seed,
            "warms"  : self.warms,
            "ntraj" : self.N_traj,
            "nsteps" : self.nsteps,
            "qhb_steps" : self.qhb_steps,
            "Ns" : self.Ns, "Nt" : self.Nt,
            "beta" : self.beta,
            "fout" : self.fout, "saveg" : self.saveg
        }
        
        # Load gauge configuration: behavior cases (starter=None -> No loadg -> fresh start)
        if isinstance(self.starter, PureGaugeORAJob):
            cmd_line_args["loadg"] = self.starter.saveg
        elif isinstance(self.starter, str):
            cmd_line_args["loadg"] = self.starter
        else:
            pass # Providing no --loadg tells the HMC runner to do a fresh start
                                 
        # Package in to JSON forest format
        self.compiled.update({
            'task_type' : 'run_script',
            'task_args' : {
                'script' : self.pg_script,
                'ncpu_fmt' : "--cpus {cpus}",
                'cmd_line_args' : cmd_line_args
            }
        })
            
            
class HMCJob(Job):
    hmc_script = 'SU4_nds_mrep.py'
    hmc_binary_path = '/path/to/hmc/binary'
    phi_binary_path = '/path/to/phi/binary'
    
    def __init__(self, Ns, Nt, beta, gammarat, k4, k6, label, count,
                 req_time,
                 N_traj, N_traj_safe, nsteps, nsteps_gauge,
                 starter, seed,
                 enable_metropolis=True,
                 nsteps2=None, shift=0.2, # Hasenbuch disabled by default
                 **kwargs):
        super(HMCJob, self).__init__(req_time=req_time, **kwargs)
        
        self.trunk = True # This is a 'trunk' job -- stream forks on these
        
        # Physical parameters
        self.Ns = Ns
        self.Nt = Nt
        self.beta = beta
        self.gammarat = gammarat
        self.k4 = k4
        self.k6 = k6
        
        self.req_time = req_time
        self.count = count
        
        # Stream/ensemble name, filesystem
        self.label = label
        self.generate_ensemble_name()
        self.generate_gaugefilename()
        self.generate_outfilename()
        
        # Deterministically generate a stream seed if none is provided
        self.seed = seed
            
        # HMC parameters
        self.enable_metropolis = enable_metropolis
        self.N_traj = N_traj
        self.N_traj_safe = N_traj_safe       
        self.nsteps = nsteps
        self.nsteps_gauge = nsteps_gauge
        
        assert (nsteps2 is None) or (shift is not None), "Must provide nsteps2 AND shift for Hasenbuch preconditioning; passed nsteps2={nsteps2} and shift={shift}".format(nsteps2=nsteps2, shift=shift)
        self.nsteps2 = nsteps2
        self.shift = shift
        
        # How to start stream
        self.starter = starter
        if isinstance(starter, HMCJob) or starter is None:
            pass
        elif isinstance(starter, str):
            assert os.path.exists(starter)
        else:
            raise Exception("Invalid starter {s}".format(s=starter))
            
    def generate_ensemble_name(self):
        self.ensemble_name = "{Ns}_{Nt}_{beta}_{k4}_{k6}_{label}".format(Ns=self.Ns, Nt=self.Nt, beta=self.beta,
                                                                         k4=self.k4, k6=self.k6, label=self.label)
    def generate_gaugefilename(self):
        self.saveg = "GaugeSU4_" + self.ensemble_name + "_{count}".format(count=self.count)
    def generate_outfilename(self):
        self.fout = "out_" + self.ensemble_name + "_{count}".format(count=self.count)
            
    def compile(self):
        super(HMCJob, self).compile()
        
        cmd_line_args = {
            "binary" : (self.hmc_binary_path if self.enable_metropolis else self.phi_binary_path),
            "seed"   : self.seed,
            "ntraj" : self.N_traj,
            "nsafe" : self.N_traj_safe,
            "nsteps1" : self.nsteps,
            "nstepsg" : self.nsteps_gauge,
            "Ns" : self.Ns, "Nt" : self.Nt,
            "beta" : self.beta, "gammarat" : self.gammarat,
            "k4" : self.k4, "k6" : self.k6,
            "fout" : self.fout, "saveg" : self.saveg
        }
        
        # Load gauge configuration: behavior cases (starter=None -> No loadg -> fresh start)
        if isinstance(self.starter, HMCJob):
            cmd_line_args["loadg"] = self.starter.saveg
        elif isinstance(self.starter, str):
            cmd_line_args["loadg"] = self.starter
        else:
            pass # Providing no --loadg tells the HMC runner to do a fresh start
        
        # Hasenbuch, if enabled
        if self.nsteps2 is not None and self.shift is not None:
            cmd_line_args['nsteps2'] = self.nsteps2
            cmd_line_args['shift'] = self.shift
                         
        # Package in to JSON forest format
        self.compiled.update({
            'task_type' : 'run_script',
            'task_args' : {
                'script' : self.hmc_script,
                'ncpu_fmt' : "--cpus {cpus}",
                'cmd_line_args' : cmd_line_args
            }
        })
        
        
class SextetHMCJob(HMCJob):
    hmc_script = 'SU4_nds_sextet.py'
    
    def __init__(self, Ns, Nt, beta, gammarat, k6, label, count,
                 req_time,
                 N_traj, N_traj_safe, nsteps, nsteps_gauge,
                 starter, seed,
                 enable_metropolis=True, k4=0, **kwargs):
        
        super(SextetHMCJob, self).__init__(Ns=Ns, Nt=Nt, beta=beta, gammarat=gammarat, k4=0,
                                           k6=k6, label=label, count=count, req_time=req_time,
                                           N_traj=N_traj, N_traj_safe=N_traj_safe, nsteps=nsteps,
                                           nsteps_gauge=nsteps_gauge, starter=starter, seed=seed,
                                           enable_metropolis=enable_metropolis, **kwargs)
                           
                           
class FundamentalHMCJob(HMCJob):
    hmc_script = 'SU4_nds_fund.py'
    
    def __init__(self, Ns, Nt, beta, gammarat, k4, label, count,
                 req_time,
                 N_traj, N_traj_safe, nsteps, nsteps_gauge,
                 starter, seed,
                 enable_metropolis=True, k6=0, **kwargs):
            
        super(FundamentalHMCJob, self).__init__(Ns=Ns, Nt=Nt, beta=beta, gammarat=gammarat, k4=k4,
                                           k6=0, label=label, count=count, req_time=req_time,
                                           N_traj=N_traj, N_traj_safe=N_traj_safe, nsteps=nsteps,
                                           nsteps_gauge=nsteps_gauge, starter=starter, seed=seed,
                                           enable_metropolis=enable_metropolis, **kwargs)
                                           


#class NstepAdjustor(Job):
#    def __init__(self, adjust_hmc_job, examine_hmc_jobs, min_AR=0.85, max_AR=0.9, die_AR=0.4, delta_nstep=1, **kwargs):
#        super(NstepAdjustor, self).__init__(req_time=0, **kwargs)
#
#        self.adjust_hmc_job = adjust_hmc_job
#        self.examine_hmc_jobs = sorted(examine_hmc_jobs, key=lambda h: h.count)
#
#        self.min_AR = min_AR
#        self.max_AR = max_AR
#        self.die_AR = die_AR
#        self.delta_nstep = delta_nstep
#        
#    def compile(self):
#        super(NstepAdjustor, self).compile()
#
#        self.compiled.update({
#            'task_type' : 'adjust_nstep',
#            'task_args' : {
#                'adjust_job' : self.adjust_hmc_job.job_id,
#                'files' : [h.fout for h in self.examine_hmc_jobs],
#                'min_AR' : self.min_AR,
#                'max_AR' : self.max_AR,
#                'die_AR' : self.die_AR,
#                'delta_nstep' : self.delta_nstep
#            }
#        })
        
        
        
class HMCAuxJob(Job):
    def __init__(self, hmc_job, req_time, **kwargs):
        assert isinstance(hmc_job, HMCJob)

        self.hmc_job = hmc_job
        self.depends_on = [hmc_job]
        
        self.Ns = hmc_job.Ns
        self.Nt = hmc_job.Nt
        
        self.ensemble_name = hmc_job.ensemble_name
        self.count = hmc_job.count
        
        self.loadg = hmc_job.saveg

        # Call super after retrieving parameters for multiple inheritance gracefulness
        super(HMCAuxJob, self).__init__(req_time=req_time, **kwargs)
        
        
        
class SpectroJob(Job):
    """Abstract class.  Needs to be subclassed in such a way
    as to fill in self.Ns, self.Nt, self.ensemble_name, and self.count before the SpectroJob
    constructor is called, or the constructor will crash.  Needs self.loadg filled in before
    compile() is called."""
    
    spectro_script = 'spectro.py'
    binary_paths = {('f',   False, False, False) : '/path/to/spectro/binary_f',
                    ('as2', False, False, False) : '/path/to/spectro/binary_as2',
                    ('f',   True,  True,  False ) : '/path/to/spectro_binary_f_p+a_screening_noBaryons'}

    def __init__(self, req_time,
                 kappa, irrep, r0,
                 cgtol=None,
                 screening=False, p_plus_a=False, do_baryons=False,
                 save_prop=False, **kwargs):
        super(SpectroJob, self).__init__(req_time=req_time, **kwargs)

        # Physical parameters        
        self.kappa = kappa
        self.r0 = r0                             

        self.screening = screening
        self.p_plus_a = p_plus_a
        self.do_baryons = do_baryons

        self.cgtol = cgtol

        # Irrep convention: f, as2
        assert (isinstance(irrep, str) and irrep.lower() in ['f', 'as2', 'a2', '4', '6']) \
            or (isinstance(irrep, int) and irrep in [4,6])
        if str(irrep).lower() in ['f', '4']:
            self.irrep = 'f'
        elif str(irrep).lower() in ['as2', 'a2', '6']:
            self.irrep = 'as2'
        
        self.generate_outfilename()
            
        if save_prop:
            self.generate_propfilename()
        else:
            self.savep = None
            
        
    def generate_outfilename(self):
        # Filesystem
        self.fout = ("x" if self.screening else "t") + "spec" + ("pa" if self.p_plus_a else "") + "_" \
            + 'r{r0:g}_'.format(r0=self.r0) \
            + '{irrep}_'.format(irrep=self.irrep) \
            + self.ensemble_name + "_" + str(self.count)
            
    def generate_propfilename(self):
        self.savep = ("XProp" if self.screening else "TProp") + ("PA" if self.p_plus_a else "") + "_" \
                + '{irrep}_'.format(irrep=self.irrep) \
                + self.ensemble_name + "_" + str(self.count)
            
    def compile(self):
        binary_key = (self.irrep, self.p_plus_a, self.screening, self.do_baryons)
        if not self.binary_paths.has_key(binary_key):
            raise Exception("Binary not specified for irrep {irrep}, p+a {p_plus_a}, screening {screening}, do_baryons {do_baryons}"\
                .format(irrep=self.irrep, p_plus_a=self.p_plus_a, screening=self.screening, do_baryons=self.do_baryons))
        
        super(SpectroJob, self).compile()
        
        cmd_line_args = {
            "Ns" : self.Ns, "Nt" : self.Nt,
            "fout" : self.fout,
            "loadg" : self.loadg,
            "binary" : self.binary_paths[binary_key],            
            "kappa" : self.kappa,
            "r0" : self.r0
        }
        
        if self.savep is not None:
            cmd_line_args["savep"] = self.savep

        if self.cgtol is not None:
            cmd_line_args["cgtol"] = self.cgtol
            
        # Package in to JSON forest format
        self.compiled.update({
            'task_type' : 'run_script',
            'task_args' : {
                'script' : self.spectro_script,
                'ncpu_fmt' : "--cpus {cpus}",
                'cmd_line_args' : cmd_line_args
            }
        })        



class FileSpectroJob(SpectroJob):
    def __init__(self, loadg,
                 req_time,
                 irrep, r0,
                 kappa=None,
                 Ns=None, Nt=None, ensemble_name=None, count=None,
                 screening=False, p_plus_a=False, do_baryons=False,
                 save_prop=False, **kwargs):

        self.loadg = loadg
        
        # Parse params from loadg; allow overriding
        parsed_params = self.parse_params_from_loadg()
        self.Ns = Ns
        if self.Ns is None:
            self.Ns = parsed_params['Ns']
        self.Nt = Nt        
        if self.Nt is None:
            self.Nt = parsed_params['Nt']
        self.count = count        
        if self.count is None:
            self.count = parsed_params['count']
        self.ensemble_name = ensemble_name        
        if self.ensemble_name is None:
            self.ensemble_name = parsed_params['ensemble_name']
        
        # Call superconstructor
        super(FileSpectroJob, self).__init__(req_time=req_time, kappa=kappa, irrep=irrep,
                                             r0=r0, screening=screening, p_plus_a=p_plus_a,
                                             do_baryons=do_baryons, save_prop=save_prop, **kwargs)
                                             
        # Provided kappa stored in self by SpectroJob constructor.
        # By default, extract appropriate kappa from hmc_job.  If specified, override for partial quenching
        if self.kappa is None:
            self.kappa = parsed_params['k4'] if self.irrep=='f' else parsed_params['k6']
    
    def parse_params_from_loadg(self):
        # e.g., GaugeSU4_12_6_7.75_0.128_0.128_1_0
        words = os.path.basename(self.loadg).split('_')
        
        return {'Ns' : int(words[1]),
                'Nt' : int(words[2]),
                'count': int(words[-1]),
                'ensemble_name' : '_'.join(words[1:-1]),
                'k4' : float(words[4]),
                'k6' : float(words[5])}
        
        
        
class HMCAuxSpectroJob(HMCAuxJob, SpectroJob):   
    def __init__(self, hmc_job,
                 irrep, r0, req_time, kappa=None,
                 screening=False, p_plus_a=False, do_baryons=False,
                 save_prop=False, **kwargs):         
        
        super(HMCAuxSpectroJob, self).__init__(hmc_job=hmc_job, req_time=req_time,
                            # Spectroscopy-relevant physical parameters
                            irrep=irrep, r0=r0, kappa=kappa,
                            screening=screening, p_plus_a=p_plus_a, do_baryons=do_baryons,
                            save_prop=save_prop, **kwargs)
                 
        # Provided kappa stored in self by SpectroJob constructor.
        # By default, extract appropriate kappa from hmc_job.  If specified, override for partial quenching
        if self.kappa is None:
            self.kappa = self.hmc_job.k4 if self.irrep=='f' else self.hmc_job.k6
        

class FlowJob(Job):
    """Abstract superclass. Needs to be subclassed in such a way that self.Ns,
    self.Nt, self.ensemble_name, self.count are filled in before the FlowJob
    constructor is called or will crash.  Needs self.loadg provided before
    compilation."""
    
    flow_script = 'flow.py'
    flow_binary_path = '/path/to/flow/binary'    
    
    def __init__(self, req_time,
                 tmax, minE=0, mindE=0, epsilon=.01, **kwargs):
        super(FlowJob, self).__init__(req_time=req_time)

        # Physical parameters
        self.tmax = tmax
        self.minE = minE
        self.mindE = mindE
        self.epsilon = epsilon
        
        # Make sure no trivial flow is run by accident
        if tmax == 0:
            assert minE != 0 or mindE != 0

        # Filesystem
        self.generate_outfilename()        
        
    def generate_outfilename(self):
        self.fout = "flow_" + self.ensemble_name + "_{count}".format(count=self.count)
            
    def compile(self):
        super(FlowJob, self).compile()
        
        cmd_line_args = {
            "Ns" : self.Ns, "Nt" : self.Nt,
            "fout" : self.fout,
            "loadg" : self.loadg,
            
            "binary" : self.flow_binary_path,
            "epsilon" : self.epsilon,
            "tmax" : self.tmax,
            "minE" : self.minE,
            "mindE" : self.mindE
        }
            
        # Package in to JSON forest format
        self.compiled.update({
            'task_type' : 'run_script',
            'task_args' : {
                'script' : self.flow_script,
                'ncpu_fmt' : "--cpus {cpus}",
                'cmd_line_args' : cmd_line_args
            }
        })


class FileFlowJob(FlowJob):
    def __init__(self, loadg, req_time,
                 tmax, minE=0, mindE=0, epsilon=.01,
                 Ns=None, Nt=None, ensemble_name=None, count=None,
                 **kwargs):

        self.loadg = loadg
        
        # Parse params from loadg; allow overriding
        parsed_params = self.parse_params_from_loadg()
        self.Ns = Ns
        if self.Ns is None:
            self.Ns = parsed_params['Ns']
        self.Nt = Nt        
        if self.Nt is None:
            self.Nt = parsed_params['Nt']
        self.count = count        
        if self.count is None:
            self.count = parsed_params['count']
        self.ensemble_name = ensemble_name        
        if self.ensemble_name is None:
            self.ensemble_name = parsed_params['ensemble_name']
        
        # Call superconstructor
        super(FileFlowJob, self).__init__(req_time=req_time, tmax=tmax, minE=minE,
                                          mindE=mindE, epsilon=epsilon, **kwargs)
    
    def parse_params_from_loadg(self):
        # e.g., GaugeSU4_12_6_7.75_0.128_0.128_1_0
        words = os.path.basename(self.loadg).split('_')
        
        return {'Ns' : int(words[1]),
                'Nt' : int(words[2]),
                'count': int(words[-1]),
                'ensemble_name' : '_'.join(words[1:-1]),
                'k4' : float(words[4]),
                'k6' : float(words[5])}


class HMCAuxFlowJob(HMCAuxJob, FlowJob):
    
    def __init__(self, hmc_job, req_time,
                 tmax, minE=0, mindE=0, epsilon=.01, **kwargs):
        super(HMCAuxFlowJob, self).__init__(hmc_job=hmc_job, req_time=req_time,
                                        tmax=tmax, minE=minE, mindE=mindE, epsilon=epsilon,
                                        **kwargs)                

        
    
class HRPLJob(Job):
    """Abstract superclass. Needs to be subclassed in such a way that self.Ns,
    self.Nt, self.ensemble_name, self.count are filled in before the HRPLJob
    constructor is called or will crash.  Needs self.loadg provided before
    compilation."""

    hrpl_script = 'hrpl.py'
    hrpl_binary_path = '/path/to/hrpl/binary'

    def __init__(self, **kwargs):
        # These should always run really fast, req_time = 2 minutes is probably overkill
        super(HRPLJob, self).__init__(req_time=120, **kwargs)
        
        self.generate_outfilename()
        
    def generate_outfilename(self):      
        self.fout = "hrpl_" + self.ensemble_name + "_{count}".format(count=self.count)
        
    def compile(self):
        super(HRPLJob, self).compile()
        
        cmd_line_args = {
            "Ns" : self.Ns, "Nt" : self.Nt,
            "fout" : self.fout,
            "loadg" : self.loadg,
            "binary" : self.hrpl_binary_path
        }
            
        # Package in to JSON forest format
        self.compiled.update({
            'task_type' : 'run_script',
            'task_args' : {
                'script' : self.hrpl_script,
                'ncpu_fmt' : "--cpus {cpus}",
                'cmd_line_args' : cmd_line_args
            }
        })


        
class HMCAuxHRPLJob(HRPLJob, HMCAuxJob):
    def __init__(self, hmc_job, **kwargs):
        super(HMCAuxHRPLJob, self).__init__(hmc_job=hmc_job, **kwargs)       
    
    
    
class FileHRPLJob(HRPLJob):
    def __init__(self, loadg,
                 Ns=None, Nt=None, ensemble_name=None, count=None,
                 **kwargs):

        self.loadg = loadg
        
        # Parse params from loadg; allow overriding
        parsed_params = self.parse_params_from_loadg()
        self.Ns = Ns
        if self.Ns is None:
            self.Ns = parsed_params['Ns']
        self.Nt = Nt        
        if self.Nt is None:
            self.Nt = parsed_params['Nt']
        self.count = count        
        if self.count is None:
            self.count = parsed_params['count']
        self.ensemble_name = ensemble_name        
        if self.ensemble_name is None:
            self.ensemble_name = parsed_params['ensemble_name']
        
        # Call superconstructor
        super(FileHRPLJob, self).__init__(**kwargs)
    
    def parse_params_from_loadg(self):
        # e.g., GaugeSU4_12_6_7.75_0.128_0.128_1_0
        words = os.path.basename(self.loadg).split('_')
        
        return {'Ns' : int(words[1]),
                'Nt' : int(words[2]),
                'count': int(words[-1]),
                'ensemble_name' : '_'.join(words[1:-1]),
                'k4' : float(words[4]),
                'k6' : float(words[5])}

        
class SpawnJob(Job):
    def __init__(self, taxi_name, taxi_time, taxi_nodes, log_dir, depends_on):
        super(SpawnJob, self).__init__(req_time=0)
        
        self.depends_on = depends_on
        
        self.taxi_name = taxi_name
        self.taxi_nodes = taxi_nodes
        self.taxi_dir = os.path.abspath(log_dir)
        self.taxi_time = taxi_time
        
    def compile(self):
        super(SpawnJob, self).compile()
        
        self.compiled.update({
                'task_type' : 'spawn',
                'task_args' : {
                    'taxi_nodes' : self.taxi_nodes,
                    'taxi_name'  : self.taxi_name,
                    'taxi_dir'   : self.taxi_dir,
                    'taxi_time'  : self.taxi_time
                }
            })
        
        
class RespawnJob(Job):
    def __init__(self):
        super(RespawnJob, self).__init__(req_time=0)
        self.status = 'recurring'

    def compile(self):
        super(RespawnJob, self).compile()
        
        self.compiled.update({
              'task_type' : 'respawn',
            })
        
### Functions for localization convenience
def specify_binary_paths(hmc_binary=None, phi_binary=None,
                         ora_binary=None,
                         flow_binary=None,
                         hrpl_binary=None):
    if hmc_binary is not None:
        HMCJob.hmc_binary_path = os.path.abspath(hmc_binary)
    if phi_binary is not None:
        HMCJob.phi_binary_path = os.path.abspath(phi_binary)
    if ora_binary is not None:
        PureGaugeORAJob.pg_binary_path = os.path.abspath(ora_binary)
    if flow_binary is not None:
        FlowJob.flow_binary_path = os.path.abspath(flow_binary)
    if hrpl_binary is not None:
        HRPLJob.hrpl_binary_path = os.path.abspath(hrpl_binary)
    
def specify_spectro_binary_path(binary, irrep, p_plus_a, screening, do_baryons):
    HMCAuxSpectroJob.binary_paths[(irrep, p_plus_a, screening, do_baryons)] = os.path.abspath(binary)
    
def specify_dir_with_runner_scripts(run_script_dir):
    run_script_dir = os.path.abspath(run_script_dir)
    
    HMCJob.hmc_script = os.path.join(run_script_dir, HMCJob.hmc_script)
    SextetHMCJob.hmc_script = os.path.join(run_script_dir, SextetHMCJob.hmc_script)
    FundamentalHMCJob.hmc_script = os.path.join(run_script_dir, FundamentalHMCJob.hmc_script)
    
    PureGaugeORAJob.pg_script = os.path.join(run_script_dir, PureGaugeORAJob.pg_script )
    
    SpectroJob.spectro_script = os.path.join(run_script_dir, SpectroJob.spectro_script)
    FlowJob.flow_script = os.path.join(run_script_dir, FlowJob.flow_script)
    HRPLJob.hrpl_script = os.path.join(run_script_dir, HRPLJob.hrpl_script)
