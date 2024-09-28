from .. databases.sars import *
from .  import *
from .. io.spc_decoder import SPCDecoder
import numpy as np
from datetime import datetime
import os

def get_profile(fname, sars_type):
    # Create a convective profile object
    # fname - filename/SARS sounding string to load in
    # sars_type - string showing what SARS database (hail/supercell) to look for the raw file
    # Load in the data
    try:
        sars_fname = getSounding(fname[0].decode('utf-8'), sars_type)
    except:
        print("Unable to find data file for:", fname[0])
        return None
    dec = SPCDecoder(sars_fname)
    profs = dec.getProfiles()
    prof = profs._profs[''][0]
    dates = profs._dates
    prof.strictQC = True
    try:
        new_prof = profile.ConvectiveProfile.copy(prof)
    except Exception as e:
        print("There was a problem with the generation of the ConvectiveProfile:", str(e))
        return None

    return new_prof

def calc_inputs(new_prof, sars_type):
    # Grab the input values for SARS that were generated by SHARPpy in the ConvectiveProfile object
    # new_prof - the ConvectiveProfile object
    # sars_type - type of SARS (hail/supercell)
    sfc_6km_shear = utils.KTS2MS( utils.mag( new_prof.sfc_6km_shear[0], new_prof.sfc_6km_shear[1]) )
    sfc_3km_shear = utils.KTS2MS( utils.mag( new_prof.sfc_3km_shear[0], new_prof.sfc_3km_shear[1]) )
    sfc_9km_shear = utils.KTS2MS( utils.mag( new_prof.sfc_9km_shear[0], new_prof.sfc_9km_shear[1]) )
    h500t = interp.temp(new_prof, 500.)
    lapse_rate = params.lapse_rate( new_prof, 700., 500., pres=True )
    right_srh3km = new_prof.right_srh3km[0]
    right_srh1km = new_prof.right_srh1km[0]
    left_srh3km = new_prof.left_srh3km[0]
    left_srh1km = new_prof.left_srh1km[0]
    mucape = new_prof.mupcl.bplus
    mlcape = new_prof.mlpcl.bplus
    mllcl = new_prof.mlpcl.lclhght
    mumr = thermo.mixratio(new_prof.mupcl.pres, new_prof.mupcl.dwpc)
    #self.ship = params.ship(self)
    if sars_type == 'supercell':
        data = [mlcape, mllcl, h500t, lapse_rate, utils.MS2KTS(sfc_6km_shear), right_srh1km, utils.MS2KTS(sfc_3km_shear), utils.MS2KTS(sfc_9km_shear), 
                right_srh3km]
    else:
        data = [ mumr, mucape, h500t, lapse_rate, sfc_6km_shear,
                sfc_9km_shear, sfc_3km_shear, right_srh3km ]
    return np.round(np.asarray(data),1)
    
def check_supercell_cal(use_db=True):
    # Use to check the SARS supercell calibration
    database_fn = os.path.join( os.path.dirname( __file__ ), 'sars_supercell.txt' )
    supercell_db = np.loadtxt(database_fn, skiprows=1, dtype=bytes, comments="%%%%") 
    hits = 0
    fa = 0
    cn = 0
    miss = 0
    match = 0
    for f in supercell_db:
        mlcape = float(f[3])
        mllcl = float(f[5])
        h5temp = float(f[9])
        lr = float(f[11])
        shr = float(f[7])
        srh = float(f[6])
        srh3 = float(f[14])
        shr3 = float(f[12])
        shr9 = float(f[13])
        if use_db is True:
            out = supercell('sars_supercell.txt', mlcape, mllcl, h5temp, lr, shr, srh, shr3, shr9, srh3)
        else:
            new_prof = get_profile(f, 'supercell')
            if new_prof is None:
                continue
            out = new_prof.right_supercell_matches
        m = int(f[0].decode('utf-8') in out[0])
        if m == 0:
            data = calc_inputs(new_prof, 'supercell')
            #print("C:", data)
            #print("T:", [mlcape, mllcl, h5temp, lr, shr, srh, shr3, shr9, srh3])
        match += m
        #print(f[0], match)
        if out[-1] >= .5 and int(f[1]) > 0:
            hits += 1
        elif out[-1] >= .5 and int(f[1]) == 0:
            fa += 1
        elif out[-1] < .5 and int(f[1]) == 0:
            cn += 1
        elif out[-1] < .5 and int(f[1]) > 0:
            miss += 1
    print("--- SARS SUPERCELL CALIBRATION ---")
    print_stats(hits, cn, miss, fa, match)
    return {'hits': hits, 'cn': cn, 'miss':miss, 'fa': fa, 'match':match}

def print_stats(hits, cn, miss, fa, matches):
    # Print out the verification stats
    print("TOTAL SNDGS:", hits + cn + miss + fa )
    print("SELF MATCHES:", matches)
    print("HIT:", hits)
    print("MISS:", miss)
    print("FALSE ALARM:", fa)
    print("CORRECT NULL:", cn)
    print("ACCURACY: %.3f" % (float(hits+cn)/float(hits+cn+miss+fa)))
    print("BIAS: %.3f" % (float(hits+fa)/float(hits+miss)))
    print("POD: %.3f" % (float(hits)/float(hits+miss)))
    print("FAR: %.3f" % (float(fa)/float(fa+hits)))
    print("CSI: %.3f" % (float(hits)/float(hits + miss + fa)))
    print("TSS: %.3f" % (float(hits)/float(hits+miss) - float(fa)/float(fa+cn)))
    print()

def calc_verification(vals):
    stats = {}
    stats['num'] = vals['hits'] + vals['cn'] + vals['miss'] + vals['fa']
    for key in vals.keys():
        stats[key] = vals[key]
    hits = stats['hits']
    miss = stats['miss']
    fa = stats['fa']
    cn = stats['cn']
    stats["ACCURACY"] = float(hits+cn)/float(hits+cn+miss+fa)
    stats["BIAS"] = float(hits+fa)/float(hits+miss)
    stats["POD"] = float(hits)/float(hits+miss)
    stats["FAR"] = float(fa)/float(fa+hits)
    stats["CSI"] = float(hits)/float(hits + miss + fa)
    stats["TSS"] = float(hits)/float(hits+miss) - float(fa)/float(fa+cn)
    return stats

def check_hail_cal(use_db=True):
    # Check the calibration of the SARS hail 
    database_fn = os.path.join( os.path.dirname( __file__ ), 'sars_hail.txt' )
    hail_db = np.loadtxt(database_fn, skiprows=1, dtype=bytes)
    hits = 0
    cn = 0
    miss = 0
    fa = 0 
    match = 0
    for f in hail_db:
        mumr = float(f[4])
        mucape = float(f[3])
        lr = float(f[7])
        h5_temp = float(f[5])
        shr = float(f[10])
        shr9 = float(f[11])
        shr3 = float(f[9])
        srh = float(f[12])
        if use_db is True:
            out = hail('sars_hail.txt', mumr, mucape, h5_temp, lr, shr, shr9, shr3, srh)
        else:
            new_prof = get_profile(f, 'hail')
            if new_prof is None:
                continue
            out = new_prof.right_matches
        m = int(f[0].decode('utf-8') in out[0])
        if m == 0:
            data = calc_inputs(new_prof, 'hail')
            #print("C:", data)
            #print("T:", [mumr, mucape, h5_temp, lr, shr, shr9, shr3, srh])
        match += m
        #print(f[0], match)
        if out[-1] >= .5 and float(f[2]) >= 2:
            hits += 1
        elif out[-1] >= .5 and float(f[2]) < 2:
            fa += 1
        elif out[-1] < .5 and float(f[2]) < 2:
            cn += 1
        elif out[-1] < .5 and float(f[2]) >= 2:
            miss += 1
    print("--- SARS HAIL CALIBRATION ---")
    print_stats(hits, cn, miss, fa, match)
    return {'hits': hits, 'cn': cn, 'miss':miss, 'fa': fa, 'match':match}

#check_db = False
#check_supercell_cal(check_db)
#check_hail_cal(check_db)