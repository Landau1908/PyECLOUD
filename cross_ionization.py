### Some thoughts:
# - Input in the machine parameters
# - We introduce a cloud_dict
import scipy.io as sio
import os
import numpy as np
from numpy.random import rand
from scipy.constants import e as qe


class Ionization_Process(object):

    def __init__(self, pyecl_input_folder, process_name, process_definitions, cloud_dict):

        # Warn if target density doesn't correspond to density of gas ionization class?

        # Decide where to take into account the mass of the projectile (if not electrons, what do you need to do?)
        # - Use actual mass of projectile here (i.e. make sure that cross sections contain scaling to electron mass if needed)

        self.name = process_name
        print('Init process %s' % self.name)
        self.target_dens = process_definitions['target_density']
        self.E_eV_init = process_definitions['E_eV_init']

        if 'extract_sigma' in process_definitions.keys():
            self.extract_sigma = process_definitions['extract_sigma']
        else:
            self.extract_sigma = True

        #  Check that ionization product names correspond to existing clouds
        product_names = process_definitions['products']
        for product in product_names:
            assert product in cloud_dict.keys(), "Product name %s does not correspond to a defined cloud name."%(product)
        self.products = product_names

        # Read cross section file
        cross_section_file = process_definitions['cross_section']

        if os.path.isfile(pyecl_input_folder + '/' + cross_section_file):
            cross_section_file_path = pyecl_input_folder + '/' + cross_section_file
        elif os.path.isfile(pyecl_input_folder + '/' + cross_section_file + '.mat'):
            cross_section_file_path = pyecl_input_folder + '/' + cross_section_file + '.mat'
        else:
            cross_section_file_path = cross_section_file

        print('Cross-section from file %s' %cross_section_file_path)

        cross_section = sio.loadmat(cross_section_file_path)

        if self.extract_sigma:
            self.extract_sigma_path = cross_section_file_path.split('.mat')[0]
            self.extract_sigma_path += '_extracted.mat'
        else:
            self.extract_sigma_path = None

        self.energy_eV = cross_section['energy_eV'].squeeze()
        self.sigma_cm2 = cross_section['cross_section_cm2'].squeeze()

        self.energy_eV_min = self.energy_eV.min()
        self.energy_eV_max = self.energy_eV.max()
        # Warn if minimum energy is not 0??

        # sey_diff is needed by the interp function
        # A 0 is appended because this last element is never needed but the array must have the correct shape
        self.sigma_cm2_diff = np.append(np.diff(self.sigma_cm2), 0.)

        flag_log = False

        # Check the energy step and define helpers for interp
        ndec_round_x = 8
        x_interp = self.energy_eV
        diff_x_interp = np.round(np.diff(x_interp), ndec_round_x)
        delta_x_interp = diff_x_interp[0]
        x_interp_min = self.energy_eV_min

        if np.any(diff_x_interp != delta_x_interp):
            # Step not linear, check if logarithmic
            x_interp = np.log10(self.energy_eV)
            diff_x_interp = np.round(np.diff(x_interp), ndec_round_x)
            delta_x_interp = diff_x_interp[0]
            x_interp_min = np.log10(self.energy_eV_min)

            if np.any(diff_x_interp != delta_x_interp):
                # Step neither linear nor logarithmic
                raise ValueError('Energy in cross section file must be equally spaced in linear or log scale.')
            else:
                flag_log = True

        self.delta_x_interp = delta_x_interp
        self.x_interp_min = x_interp_min
        self.flag_log = flag_log


    def generate(self, Dt, cloud_dict, mass_proj, N_proj, nel_mp_proj,
                 x_proj, y_proj, z_proj, v_mp_proj, flag_generate=True):

        E_eV_mp_proj = 0.5 * mass_proj / qe * v_mp_proj * v_mp_proj

        # Get sigma
        sigma_mp_proj = self.get_sigma(energy_eV_proj=E_eV_mp_proj)

        # Compute N_mp to add
        DN_per_proj = sigma_mp_proj * self.target_dens * v_mp_proj * Dt * nel_mp_proj

        N_proj = len(nel_mp_proj)

        for product in self.products:

            thiscloud_gen = cloud_dict[product]
            MP_e_gen = thiscloud_gen.MP_e
            nel_mp_ref_gen = MP_e_gen.nel_mp_ref
            mass_gen = MP_e_gen.mass

            # For now initialize generated MPs with velocity determined by input initial energy -
            # similarly to gas ionization
            v0_gen = np.sqrt(2 * (self.E_eV_init / 3.) * qe / mass_gen)

            N_mp_per_proj_float = DN_per_proj / nel_mp_ref_gen
            N_mp_per_proj_int = np.floor(N_mp_per_proj_float)
            rest = N_mp_per_proj_float - N_mp_per_proj_int
            N_mp_per_proj_int = np.int_(N_mp_per_proj_int)
            N_mp_per_proj_int += np.int_(rand(N_proj) < rest)

            N_new_MPs = np.sum(N_mp_per_proj_int)

            if N_new_MPs > 0:
                mask_gen = N_mp_per_proj_int > 0
                N_mp_per_proj_int_masked = N_mp_per_proj_int[mask_gen]

                # nel_new_MPs_masked = np.zeros(np.sum(mask_gen))
                # nel_new_MPs_masked = DN_per_proj[mask_gen] / np.float_(N_mp_per_proj_int_masked)
                nel_new_MPs_masked = np.ones(np.sum(mask_gen)) * nel_mp_ref_gen  # alternative

                nel_new_MPs = np.repeat(nel_new_MPs_masked, N_mp_per_proj_int_masked)

                # print('Energy = %f, DN_per_proj = %f, nel_mp_ref = %f, N_mp_per_proj_float = %f, N_mp_per_proj_int = %.f, nel_new_mps = %f,  N_new_MPs = %d' \
                #       %(E_eV_mp_proj[mask_gen][0], DN_per_proj[mask_gen][0], nel_mp_ref_gen, N_mp_per_proj_float[mask_gen][0], N_mp_per_proj_int[mask_gen][0], nel_new_MPs[0],  N_new_MPs))

                x_masked = x_proj[mask_gen]
                y_masked = y_proj[mask_gen]
                z_masked = z_proj[mask_gen]

                x_new_MPs = np.repeat(x_masked, N_mp_per_proj_int_masked)
                y_new_MPs = np.repeat(y_masked, N_mp_per_proj_int_masked)
                z_new_MPs = np.repeat(z_masked, N_mp_per_proj_int_masked)

                vx_new_MPs = np.zeros(N_new_MPs)
                vy_new_MPs = np.zeros(N_new_MPs)
                vz_new_MPs = np.zeros(N_new_MPs)

                vx_new_MPs = v0_gen * (rand(N_new_MPs) - 0.5)
                vy_new_MPs = v0_gen * (rand(N_new_MPs) - 0.5)
                vz_new_MPs = v0_gen * (rand(N_new_MPs) - 0.5)

            else:
                nel_new_MPs = np.array([])
                x_new_MPs = np.array([])
                y_new_MPs = np.array([])
                z_new_MPs = np.array([])
                vx_new_MPs = np.array([])
                vy_new_MPs = np.array([])
                vz_new_MPs = np.array([])

            if flag_generate and N_new_MPs > 0:
                # Generate new MPs
                print('Generating %d MPs in cloud %s' %(N_new_MPs, product))
                t_last_impact = -1
                MP_e_gen.add_new_MPs(N_new_MPs, nel_new_MPs, x_new_MPs,
                                     y_new_MPs, z_new_MPs, vx_new_MPs,
                                     vy_new_MPs, vz_new_MPs, t_last_impact)
            else:
                # We don't generate, just return numbers to generate
                return N_new_MPs, nel_new_MPs



    def get_sigma(self, energy_eV_proj):

        sigma_cm2_proj = energy_eV_proj * 0.

        # For now we set sigma = 0. both below and above energies in file...
        mask_below = (energy_eV_proj < self.energy_eV_min)
        mask_above = (energy_eV_proj > self.energy_eV_max)
        mask_interp = ~mask_below * ~mask_above

        if self.flag_log:
            x_interp_proj = np.log10(energy_eV_proj[mask_interp])
        else:
            x_interp_proj = energy_eV_proj[mask_interp]

        sigma_cm2_proj[mask_interp] = self._interp(x_interp_proj=x_interp_proj)

        # Return cross section in m2
        return sigma_cm2_proj * 1e-4 


    def _interp(self, x_interp_proj):
        """
        Linear interpolation of the energy - sigma curve.
        """
        index_float = (x_interp_proj - self.x_interp_min) / self.delta_x_interp
        index_remainder, index_int = np.modf(index_float)
        index_int = index_int.astype(int)

        return self.sigma_cm2[index_int] + index_remainder * self.sigma_cm2_diff[index_int]



class Cross_Ionization(object):

    def __init__(self, pyecl_input_folder, cross_ion_definitions, cloud_list):
        
        print('Initializing cross ionization.')

        # Make cloud dict from list
        cloud_dict = {}
        for cloud in cloud_list:
            cloud_dict.update({cloud.name : cloud})

        self.projectiles_dict = {}

        # Init projectiles
        for projectile in cross_ion_definitions.keys():
            print('Projectile %s:' %(projectile))
 
           # Check that projectile name corresponds to existing cloud
            assert projectile in cloud_dict.keys(), "Projectile name %s does not correspond to a defined cloud name."%(projectile)

            self.projectiles_dict.update({projectile : []})

            # Init processes
            for process_name in cross_ion_definitions[projectile].keys():
                process_definitions = cross_ion_definitions[projectile][process_name]
                process = Ionization_Process(pyecl_input_folder, process_name, process_definitions, cloud_dict)

                self.projectiles_dict[projectile].append(process)

        # Extract sigma curves for consistency checks
        n_rep = 100000
        Dt_test = 25e-9 #s?
        # energy_eV_test = np.append(np.arange(0, 999., 1.), np.arange(1000., 20100, 5))
        energy_eV_test = np.logspace(np.log10(1.), np.log10(25000.), num=5000)

        self._extract_sigma(Dt=Dt_test, cloud_dict=cloud_dict,
                            n_rep=n_rep, energy_eV=energy_eV_test)


    def generate(self, Dt, cloud_list):
        
        # Make cloud dict from list
        cloud_dict = {}
        for cloud in cloud_list:
            cloud_dict.update({cloud.name : cloud})

        for projectile in self.projectiles_dict.keys():
            
            thiscloud = cloud_dict[projectile]
            MP_e = thiscloud.MP_e
            N_mp = MP_e.N_mp
            mass = MP_e.mass

            if N_mp > 0:

                nel_mp = MP_e.nel_mp[:N_mp]

                x_mp = MP_e.x_mp[:N_mp]
                y_mp = MP_e.y_mp[:N_mp]
                z_mp = MP_e.z_mp[:N_mp]

                vx_mp = MP_e.vx_mp[:N_mp]
                vy_mp = MP_e.vy_mp[:N_mp]
                vz_mp = MP_e.vz_mp[:N_mp]

                v_mp = np.sqrt(vx_mp * vx_mp +
                               vy_mp * vy_mp +
                               vz_mp * vz_mp)

                for process in self.projectiles_dict[projectile]:

                    process.generate(Dt=Dt, cloud_dict=cloud_dict,
                                     mass_proj=mass, N_proj=N_mp,
                                     nel_mp_proj=nel_mp, x_proj=x_mp,
                                     y_proj=y_mp, z_proj=z_mp, v_mp_proj=v_mp)


    def _extract_sigma(self, Dt, cloud_dict, n_rep, energy_eV):

        v0 = 0.
        N_ene = len(energy_eV)

        N_mp = n_rep

        x_mp = np.zeros(n_rep)
        y_mp = np.zeros(n_rep)
        z_mp = np.zeros(n_rep)

        for projectile in self.projectiles_dict.keys():

            thiscloud = cloud_dict[projectile]
            mass = thiscloud.MP_e.mass
            nel_mp = np.ones(n_rep) * thiscloud.MP_e.nel_mp_ref

            v_test = np.sqrt(2 * energy_eV * qe / mass)

            for process in self.projectiles_dict[projectile]:

                if process.extract_sigma:

                    print('Extracting cross section for process %s' %process.name )

                    save_dict = {}
                    save_dict['energy_eV'] = energy_eV
                    save_dict['sigma_cm2_interp'] = np.zeros(len(energy_eV))
                    save_dict['sigma_cm2_sampled'] = np.zeros(len(energy_eV))

                    for i_ene, energy in enumerate(energy_eV):

                        if np.mod(i_ene, N_ene / 10) == 0:
                            print ('Extracting sigma %.0f'%(float(i_ene) / float(N_ene) * 100) + """%""")

                        # Test process.get_sigma()
                        sigma_m2 = process.get_sigma(np.array([energy]))
                        save_dict['sigma_cm2_interp'][i_ene] = sigma_m2 * 1e4

                        # Test process.generate()
                        v_ene = v_test[i_ene]
                        v_mp = v_ene * np.ones(n_rep)

                        N_new_MPs, nel_new_MPs \
                            = process.generate(Dt, cloud_dict=cloud_dict,
                                               mass_proj=mass, N_proj=N_mp,
                                               nel_mp_proj=nel_mp, x_proj=x_mp,
                                               y_proj=y_mp, z_proj=z_mp,
                                               v_mp_proj=v_mp, flag_generate=False)

                        DN_gen = np.sum(nel_new_MPs)
                        if v_ene > 0:
                            sigma_m2_est = DN_gen / process.target_dens / v_ene / Dt / np.sum(nel_mp)
                            # print('DN_gen = %f, nel_mp = %f, sum(nel_mp) = %f' %(DN_gen, nel_mp[0], np.sum(nel_mp)))
                        else:
                            sigma_m2_est = 0.
                        save_dict['sigma_cm2_sampled'][i_ene] = sigma_m2_est * 1e4

                    sio.savemat(process.extract_sigma_path, save_dict, oned_as='row')
                    print('Saved extracted cross section as %s' %process.extract_sigma_path)


