import os


### Job classes
class Job(object):
    def __init__(self, req_time=0):
        self.depends_on = []
        self.req_time = req_time
        self.status = 'pending'
        self.trunk = False
        
    def compile(self):
        # Package in to JSON forest format
        self.compiled = {
            'id'        : self.job_id,
            'req_time'  : self.req_time,
            'status'    : self.status,
        }
        
        # Get dependencies in job_id format
        if self.depends_on is None or len(self.depends_on) == 0:
            self.compiled['depends_on'] = None
        else:
            self.compiled['depends_on'] = [d.job_id for d in self.depends_on]
            

class CopyJob(Job):
    def __init__(self, src, dest, req_time=60):
        super(CopyJob, self).__init__(req_time=req_time)
        
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
            
class HMCJob(Job):
    hmc_script = './SU4_nds_mrep.py'
    hmc_binary_path = '/path/to/hmc/binary'
    phi_binary_path = '/path/to/phi/binary'
    
    def __init__(self, Ns, Nt, beta, gammarat, k4, k6, label, count,
                 req_time,
                 N_traj, N_traj_safe, nsteps, nsteps_gauge,
                 starter, seed,
                 enable_metropolis=True):
        super(HMCJob, self).__init__(req_time=req_time)
        
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
        
        # Package in to JSON forest format
        self.compiled.update({
            'task_type' : 'run_script',
            'task_args' : {
                'script' : self.hmc_script,
                'ncpu_fmt' : "--cpus {cpus}",
                'cmd_line_args' : cmd_line_args
            }
        })


class NstepAdjustor(Job):
    def __init__(self, adjust_hmc_job, examine_hmc_jobs, min_AR=0.75, max_AR=0.85, die_AR=0.4, delta_nstep=1):
        super(NstepAdjustor, self).__init__(req_time=0)

        self.adjust_hmc_job = adjust_hmc_job
        self.examine_hmc_jobs = sorted(examine_hmc_jobs, key=lambda h: h.count)

        self.min_AR = min_AR
        self.max_AR = max_AR
        self.die_AR = die_AR
        self.delta_nstep = delta_nstep
        
    def compile(self):
        super(NstepAdjustor, self).compile()

        self.compiled.update({
            'task_type' : 'adjust_nstep',
            'task_args' : {
                'adjust_job' : self.adjust_hmc_job.job_id,
                'files' : [h.fout for h in self.examine_hmc_jobs],
                'min_AR' : self.min_AR,
                'max_AR' : self.max_AR,
                'die_AR' : self.die_AR,
                'delta_nstep' : self.delta_nstep
            }
        })
        
        
class HMCAuxJob(Job):
    def __init__(self, hmc_job, req_time):
        assert isinstance(hmc_job, HMCJob)
        super(HMCAuxJob, self).__init__(req_time=req_time)

        self.hmc_job = hmc_job
        self.depends_on = [hmc_job]
        
        self.Ns = hmc_job.Ns
        self.Nt = hmc_job.Nt
        
        self.ensemble_name = hmc_job.ensemble_name
        self.count = hmc_job.count
        
        self.loadg = hmc_job.saveg
        
        
class HMCAuxSpectroJob(HMCAuxJob):
    spectro_script = './spectro.py'
    binary_paths = {('f',   False, False, False) : '/path/to/spectro/binary_f',
                    ('as2', False, False, False) : '/path/to/spectro/binary_as2',
                    ('f',   True,  True,  False ) : '/path/to/spectro_binary_f_p+a_screening_noBaryons'}
    
    def __init__(self, hmc_job,
                 irrep, r0, req_time, kappa=None,
                 screening=False, p_plus_a=False, do_baryons=False,
                 save_prop=False):
        super(HMCAuxSpectroJob, self).__init__(hmc_job=hmc_job, req_time=req_time)
        
        # Irrep convention: f, as2
        assert (isinstance(irrep, str) and irrep.lower() in ['f', 'as2', 'a2', '4', '6']) \
            or (isinstance(irrep, int) and irrep in [4,6])
        if str(irrep).lower() in ['f', '4']:
            self.irrep = 'f'
        elif str(irrep).lower() in ['as2', 'a2', '6']:
            self.irrep = 'as2'
        
        # Physical parameters
        self.kappa = kappa
        if self.kappa is None:
            self.kappa = hmc_job.k4 if irrep=='f' else hmc_job.k6
        self.r0 = r0
        self.screening = screening
        self.p_plus_a = p_plus_a
        self.do_baryons = do_baryons
        
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
        
        super(HMCAuxSpectroJob, self).compile()
        
        cmd_line_args = {
            "Ns" : self.Ns, "Nt" : self.Nt,
            "fout" : self.fout,
            "loadg" : self.loadg,
            "binary" : self.binary_paths[binary_key],            
            "kappa" : self.kappa,
            "r0" : self.r0
        }
        
        if self.savep is not None:
            cmd_line_args.append("--savep %s"%self.savep)
            
        # Package in to JSON forest format
        self.compiled.update({
            'task_type' : 'run_script',
            'task_args' : {
                'script' : self.spectro_script,
                'ncpu_fmt' : "--cpus {cpus}",
                'cmd_line_args' : cmd_line_args
            }
        })
        
        
class HMCAuxFlowJob(HMCAuxJob):
    flow_script = './flow.py'
    flow_binary_path = '/path/to/flow/binary'
    
    def __init__(self, hmc_job, tmax, req_time, minE=0, mindE=0, epsilon=.01):
        super(HMCAuxFlowJob, self).__init__(hmc_job=hmc_job, req_time=req_time)
        
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
        super(HMCAuxFlowJob, self).compile()
        
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
        
        
        
class HMCAuxHRPLJob(HMCAuxJob):
    hrpl_script = './hrpl.py'
    hrpl_binary_path = '/path/to/hrpl/binary'
    
    def __init__(self, hmc_job):
        # These should always run really fast, req_time = 2 minutes is probably overkill
        super(HMCAuxHRPLJob, self).__init__(hmc_job=hmc_job, req_time=120)
        
        self.generate_outfilename()
        
    def generate_outfilename(self):      
        self.fout = "hrpl_" + self.ensemble_name + "_{count}".format(count=self.count)
        
    def compile(self):
        super(HMCAuxHRPLJob, self).compile()
        
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
                         flow_binary=None,
                         hrpl_binary=None):
    if hmc_binary is not None:
        HMCJob.hmc_binary_path = os.path.abspath(hmc_binary)
    if phi_binary is not None:
        HMCJob.phi_binary_path = os.path.abspath(phi_binary)
    if flow_binary is not None:
        HMCAuxFlowJob.flow_binary_path = os.path.abspath(flow_binary)
    if hrpl_binary is not None:
        HMCAuxHRPLJob.hrpl_binary_path = os.path.abspath(hrpl_binary)
    
def specify_spectro_binary_path(binary, irrep, p_plus_a, screening, do_baryons):
    HMCAuxSpectroJob.binary_paths[(irrep, p_plus_a, screening, do_baryons)] = os.path.abspath(binary)
    
def specify_dir_with_runner_scripts(run_script_dir):
    run_script_dir = os.path.abspath(run_script_dir)
    
    HMCJob.hmc_script = run_script_dir + '/SU4_nds_mrep.py'
    HMCAuxSpectroJob.spectro_script = run_script_dir + '/spectro.py'
    HMCAuxFlowJob.flow_script = run_script_dir + '/flow.py'
    HMCAuxHRPLJob.hrpl_script = run_script_dir + '/hrpl.py'