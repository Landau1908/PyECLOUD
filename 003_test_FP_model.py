import numpy as np
import matplotlib.pyplot as plt

import sec_emission_model_furman_pivi as fp

import mystyle as ms

plt.close('all')
ms.mystyle(12)

test_obj = fp.SEY_model_FP_Cu(10)

#energies = np.exp(np.linspace(np.log(1e-3), np.log(3e3), int(1e4)))
energies = np.linspace(0, 800, int(1e5))

angles = 0.

delta_e, delta_r, delta_ts, delta_mc, loc = test_obj.SEY_process(None, energies, angles, None)

delta = delta_e + delta_r + delta_ts


fig = ms.figure('Test Furman Pivi model')

sp = plt.subplot(2,2,1)
sp.grid(True)
#sp.set_xscale('log')

delta_mc_2 = np.zeros_like(delta_mc)
n_indices = np.sum(energies < 10)
for ctr, ener in enumerate(energies):
    min_index = max(0, ctr - n_indices/2)
    max_index = min(len(energies), ctr + n_indices/2)
    delta_mc_2[ctr] = np.mean(delta_mc[min_index:max_index])


sp.plot(energies, delta_e, label='Backscattered')
sp.plot(energies, delta_r, label='Rediffused')
sp.plot(energies, delta_ts, label='True secondaries')
sp.plot(energies, delta, label='Total')
sp.plot(energies, delta_mc_2)

sp.legend(title='Emitted electrons')

plt.show()
