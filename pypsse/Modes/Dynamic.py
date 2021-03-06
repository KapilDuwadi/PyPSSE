import numpy as np
import os
from pypsse.Modes.abstract_mode import AbstractMode
import datetime
class Dynamic(AbstractMode):

    def __init__(self,psse, dyntools, settings, export_settings, logger):
        super().__init__(psse, dyntools, settings, export_settings, logger)
        self.time = datetime.datetime.strptime(settings["Start time"], "%m/%d/%Y %H:%M:%S")
        self.incTime = settings["Step resolution (sec)"]
        return

    def init(self, bus_subsystems):
        super().init(bus_subsystems)
        if len(self.settings["Setup files"]):
            ierr = None
            for f in self.settings["Setup files"]:
                setup_path = os.path.join(self.settings["Project Path"], 'Case_study', f)
                ierr = self.PSSE.runrspnsfile(setup_path)
                if ierr:
                    raise Exception('Error running setup file "{}"'.format(setup_path))
                else:
                    self.logger.debug('Setup file {} sucessfully run'.format(setup_path))

        else:
            if len(self.settings["Rwm file"]):
                self.PSSE.mcre([1, 0], self.rwn_file)

            self.convert_load()
            self.PSSE.cong(0)
            # Solve for dynamics
            self.PSSE.ordr(0)
            self.PSSE.fact()
            self.PSSE.tysl(0)
            self.PSSE.tysl(0)
            self.PSSE.save(self.study_case_path.split('.')[0] + ".sav")
            self.logger.debug('Loading dynamic model....')
            ierr = self.PSSE.dyre_new([1, 1, 1, 1], self.dyr_path, '', '', '')
            if ierr:
                raise Exception('Error loading dynamic model file "{}"'.format(self.dyr_path))
            else:
                self.logger.debug('Dynamic file {} sucessfully loaded'.format(self.dyr_path))

            if self.export_settings["Export results using channels"]:
                self.setup_channels()

            self.PSSE.snap(sfile=self.snp_file)
            # Load user defined models
            for mdl in self.settings["User models"]:
                dll_path = os.path.join(self.settings["Project Path"], 'Case_study', mdl)
                self.PSSE.addmodellibrary(dll_path)
                self.logger.debug('User defined library added: {}'.format(mdl))
            # Load flow settings
            self.PSSE.fdns([0, 0, 0, 1, 1, 0, 99, 0])
        # initialize
        iErr = self.PSSE.strt_2([1, self.settings["Generators"]["Missing machine model"]], self.outx_path)
        if iErr:
            self.initialization_complete = False
            raise Exception('Dynamic simulation failed to successfully initialize')
        else:
            self.initialization_complete = True
            self.logger.debug('Dynamic simulation initialization sucess!')
        # get load info for the sub system
        self.load_info = self.get_load_indices(bus_subsystems)
        self.logger.debug('pyPSSE initialization complete!')
        return self.initialization_complete

    def step(self, t):
        self.time = self.time + datetime.timedelta(seconds=self.incTime)
        return self.PSSE.run(0, t, 1, 1, 1)

    def get_load_indices(self, bus_subsystems):
        all_bus_ids = {}
        for id in bus_subsystems.keys():
            load_info = {}
            ierr, load_data = self.PSSE.aloadchar(id, 1, ['ID', 'NAME', 'EXNAME'])
            load_data = np.array(load_data)
            ierr, bus_data = self.PSSE.aloadint(id, 1, ['NUMBER'])
            bus_data = bus_data[0]
            for i, bus_id in enumerate(bus_data):
                load_info[bus_id] = {
                    'Load ID' : load_data[0,i],
                    'Bus name' : load_data[1,i],
                    'Bus name (ext)' : load_data[2,i],
                }
            all_bus_ids[id] = load_info
        return all_bus_ids

    def convert_load(self, busSubsystem= None):
        if self.settings['Loads']['Convert']:
            P1 = self.settings['Loads']['active_load']["% constant current"]
            P2 = self.settings['Loads']['active_load']["% constant admittance"]
            Q1 = self.settings['Loads']['reactive_load']["% constant current"]
            Q2 = self.settings['Loads']['reactive_load']["% constant admittance"]
            if busSubsystem:
                self.PSSE.conl(busSubsystem, 0, 1, [0, 0], [P1, P2, Q1, Q2]) # initialize for load conversion.
                self.PSSE.conl(busSubsystem, 0, 2, [0, 0], [P1, P2, Q1, Q2]) # convert loads.
                self.PSSE.conl(busSubsystem, 0, 3, [0, 0], [P1, P2, Q1, Q2]) # postprocessing housekeeping.
            else:
                self.PSSE.conl(0, 1, 1, [0, 0], [P1, P2, Q1, Q2]) # initialize for load conversion.
                self.PSSE.conl(0, 1, 2, [0, 0], [P1, P2, Q1, Q2]) # convert loads.
                self.PSSE.conl(0, 1, 3, [0, 0], [P1, P2, Q1, Q2]) # postprocessing housekeeping.

