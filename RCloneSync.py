#!/usr/bin/env python
#========================================================== 
#
#  Basic BiDirectional Sync using RClone
#
#  Usage
#   Configure rclone, including authentication before using this tool.  rclone must be in the search path.
#
#  Chris Nelson, August 2017
#
# 170805  Added --Verbose command line switch 
# 170730  Horrible bug - remote lsl failing results in deleting all local files, and then iteratively replicating _LOCAL and _REMOTE files.
#       Added connection test/checking files to abort if the basic connection is down.  RCLONE_TEST files on the local system
#       must match the remote system (and be unchanged), else abort.
#       Added lockfile so that a second run aborts if a first run is still in process, or failed and left the lockfile in place.
#       Added python logging, sorted processing
# 170716  New
#
# Known bugs:
#   Cannot directly compare timestamps on remote and local.  Modification time not retained when a file is transferred.
#   rclone sync pushes files from local to remote based on size differences.  If a local file is changed but same size it wont be pushed.
#   the try/except blocks around rclone are not effective for catching rclone errors.  It seems rclone always exits with 0 status
#   Size difference identified but not handled
#   Older version found but not handled
#   If same timestamp file is added to both cloud and local then ???
#
#==========================================================

import argparse
import sys
import re
import os.path, subprocess
from datetime import datetime
import time
import shlex
import logging
import collections                          # dictionary sorting 

localWD =    "/home/xxx/RCloneSyncWD/"      # File lists for the local and remote trees as of last sync, etc. 

logging.basicConfig(format='%(asctime)s/%(levelname)s:  %(message)s')   # /%(module)s/%(funcName)s


def main():

    excludes = ' '
    if exclusions:
        if not os.path.exists(exclusions):
            logging.error ("Specified Exclusions file does not exist:  " + exclusions)
            return 1
        excludes = " --exclude-from " + exclusions + ' '

    localListFile  = localWD + remoteName[0:-1] + '_localLSL'          # Delete the ':' on the end
    remoteListFile = localWD + remoteName[0:-1] + '_remoteLSL'

    _dryRun = ' '
    if dryRun:
        _dryRun = '--dry-run'       # string used on rclone invocations
        if os.path.exists (localListFile):
            subprocess.call (['cp', localListFile, localListFile + 'DRYRUN'])
            localListFile  += 'DRYRUN'
        if os.path.exists (remoteListFile):
            subprocess.call (['cp', remoteListFile, remoteListFile + 'DRYRUN'])
            remoteListFile += 'DRYRUN'


    # ***** Generate initial local and remote file lists, and copy any unique Remote files to Local *****
    if firstSync:
        logging.info (">>>>> Generating --FirstSync Local and Remote lists")
        try:
            with open(localListFile, "w") as of:
                subprocess.call(shlex.split("rclone lsl " + localRoot + excludes), stdout=of)
        except:
            logging.error (printMsg ("*****", "Specified --LocalRoot invalid?", "<{}>".format(localRoot)))
            return 1

        try:
            with open(remoteListFile, "w") as of:
                subprocess.call(shlex.split("rclone lsl " + remoteNameSP + excludes), stdout=of)
        except:
            logging.error (printMsg ("*****", "Specified --Cloud invalid?", remoteName))
            return 1

        localNow  = loadList (localListFile)
        remoteNow = loadList (remoteListFile)

        for key in remoteNow:
            if key not in localNow:
                src  = '"' + remoteName + key + '" '           # Extra space for shlex.split
                dest = '"' + localRoot + '/' + key + '" '
                logging.info (printMsg ("REMOTE", "  Copying to local", dest))
                subprocess.call(shlex.split("rclone copyto " + src + dest + _dryRun))

        with open(localListFile, "w") as of:            # Update local list file, then fall into regular sync
            subprocess.call(shlex.split("rclone lsl " + localRootSP + excludes), stdout=of)


    # ***** Check basic health of access to the local and remote filesystems *****
    logging.info (">>>>> Checking rclone Local and Remote access health")
    localChkListFile  = localWD + remoteName[0:-1] + '_localChkLSL'          # Delete the ':' on the end
    remoteChkListFile = localWD + remoteName[0:-1] + '_remoteChkLSL'
    chkFile = 'RCLONE_TEST'

    try:
        with open(localChkListFile, "w") as of:
            subprocess.call(shlex.split("rclone lsl " + localRootSP + '--include ' + chkFile), stdout=of)
    except:
        logging.error (printMsg ("*****", "Specified --LocalRoot invalid?", "<{}>".format(localRoot)))
        return 1

    try:
        with open(remoteChkListFile, "w") as of:
            subprocess.call(shlex.split("rclone lsl " + remoteNameSP + '--include ' + chkFile), stdout=of)
    except:
        logging.error (printMsg ("*****", "Specified --Cloud invalid?", remoteName))
        return 1

    localCheck  = loadList (localChkListFile)
    remoteCheck = loadList (remoteChkListFile)

    if len(localCheck) < 1 or len(localCheck) != len(remoteCheck):
        logging.error (printMsg ("*****", "Failed access health test:  <{}> local count {}, remote count {}"
                                 .format(chkFile, len(localCheck), len(remoteCheck)), ""))
        return 1
    else:
        for key in localCheck:
            logging.debug ("Check key " + key)
            if key not in remoteCheck:
                logging.error (printMsg ("*****", "Failed access health test:  Local key <{}> not found in remote".format(key), ""))
                return 1

    os.remove(localChkListFile)
    os.remove(remoteChkListFile)
    

    # ***** Get current listings of the local and remote trees *****
    logging.info (">>>>> Generating Local and Remote lists")

    localListFileNew = localWD + remoteName[0:-1] + '_localLSL_new'
    try:
        with open(localListFileNew, "w") as of:
            subprocess.call(shlex.split("rclone lsl " + localRootSP + excludes), stdout=of)
    except:
        logging.error (printMsg ("*****", "Specified --LocalRoot invalid?", "<{}>".format(localRoot)))
        return 1

    remoteListFileNew = localWD + remoteName[0:-1] + '_remoteLSL_new'
    try:
        with open(remoteListFileNew, "w") as of:
            subprocess.call(shlex.split("rclone lsl " + remoteNameSP + excludes), stdout=of)
    except:
        logging.error (printMsg ("*****", "Specified --Cloud invalid?", localRoot))
        return 1


    # ***** Load Current and Prior listings of both Local and Remote trees *****
    localPrior = loadList (localListFile)
    remotePrior = loadList (remoteListFile)

    localNow = loadList (localListFileNew)
    remoteNow = loadList (remoteListFileNew)


    # ***** Check both local and remote for change relative to the last sync *****
    # Older note.  ^ indicates scenarios covered
    # Scenarios:  (^ are implemented)
    #    ^  'newLocal'          Does not exist on remote.  Copy to remote.
    #    ^  'newerLocal'        Local is newer than prior local and remote unchanged.  Copy to remote.
    #       'olderLocal'        Local is older than prior local and current remote.  Rename local to _LOCAL, and copy remote to local.
    #       'sizeLocal'         Local size has changed with no date change.  DO WHAT?
    #    ^  'deletedLocal'      Local no longer exists and remote unchanged:  Delete on remote, else copy remote to local with _REMOTE.
    #    ^  'newRemote'         Does not exist on local.  Copy to local.
    #    ^  'newerRemote'       Remote is newer than prior remote and local unchanged:  Copy to local.
    #       'olderRemote'       Remote is older than prior remote and current local:  Copy to local with _REMOTE
    #       'sizeRemote'        Remote size has changed with no date change.  DO WHAT?
    #    ^  'deletedRemote'     Remote no longer exists and local unchanged:  Delete on local, else rename on local with _LOCAL.
    #    ^  'newerBoth'         Both local and remote have newer versions than prior sync.  Copy remote to local with _REMOTE.


    # ***** Check for LOCAL deltas relative to the prior sync
    logging.info (printMsg ("LOCAL", "Checking for Diffs", localRoot))
    localDeltas = {}
    for key in localPrior:
        _newer=False; _older=False; _size=False; _deleted=False
        if key not in localNow:
            logging.info (printMsg ("LOCAL", "  File was deleted", key))
            _deleted=True            
        else:
            if localPrior[key]['datetime'] != localNow[key]['datetime']:
                if localPrior[key]['datetime'] < localNow[key]['datetime']:
                    logging.info (printMsg ("LOCAL", "  File is newer", key))
                    _newer=True
                else:               # Now local version is older than prior sync
                    logging.info (printMsg ("LOCAL", "  File is OLDER", key))
                    _older=True
            if localPrior[key]['size'] != localNow[key]['size']:
                logging.info (printMsg ("LOCAL", "  File size is different", key))
                _size=True

        if _newer or _older or _size or _deleted:
            localDeltas[key] = {'new':False, 'newer':_newer, 'older':_older, 'size':_size, 'deleted':_deleted}

    for key in localNow:
        if key not in localPrior:
            logging.info (printMsg ("LOCAL", "  File is new", key))
            localDeltas[key] = {'new':True, 'newer':False, 'older':False, 'size':False, 'deleted':False}

    localDeltas = collections.OrderedDict(sorted(localDeltas.items()))      # sort the deltas list
    if len(localDeltas) > 0:
        logging.warning ("  {:4} file change(s) on the Local system {}".format(len(localDeltas), localRoot))


    # ***** Check for REMOTE deltas relative to the last sync
    logging.info (printMsg ("REMOTE", "Checking for Diffs", remoteName))
    remoteDeltas = {}
    for key in remotePrior:
        _newer=False; _older=False; _size=False; _deleted=False
        if key not in remoteNow:
            logging.info (printMsg ("REMOTE", "  File was deleted", key))
            _deleted=True            
        else:
            if remotePrior[key]['datetime'] != remoteNow[key]['datetime']:
                if remotePrior[key]['datetime'] < remoteNow[key]['datetime']:
                    logging.info (printMsg ("REMOTE", "  File is newer", key))
                    _newer=True
                else:               # Now remote version is older than prior sync 
                    logging.info (printMsg ("REMOTE", "  File is OLDER", key))
                    _older=True
            if remotePrior[key]['size'] != remoteNow[key]['size']:
                logging.info (printMsg ("REMOTE", "  File size is different", key))
                _size=True

        if _newer or _older or _size or _deleted:
            remoteDeltas[key] = {'new':False, 'newer':_newer, 'older':_older, 'size':_size, 'deleted':_deleted}

    for key in remoteNow:
        if key not in remotePrior:
            logging.info (printMsg ("REMOTE", "  File is new", key))
            remoteDeltas[key] = {'new':True, 'newer':False, 'older':False, 'size':False, 'deleted':False}

    remoteDeltas = collections.OrderedDict(sorted(remoteDeltas.items()))    # sort the deltas list
    if len(remoteDeltas) > 0:
        logging.warning ("  {:4} file change(s) on {}".format(len(remoteDeltas), remoteName))


    # ***** Update LOCAL with all the changes on REMOTE *****
    if len(remoteDeltas) == 0:
        logging.info (">>>>> No changes on Remote - Skipping ahead")
    else:
        logging.info (">>>>> Applying changes on Remote to Local")

    for key in remoteDeltas:
        if remoteDeltas[key]['new']:
            #logging.info (printMsg ("REMOTE", "  New file", key))
            if key not in localNow: #localDeltas:
                src  = '"' + remoteName + key + '" '
                dest = '"' + localRoot + '/' + key + '" '
                logging.info (printMsg ("REMOTE", "  Copying to local", dest))
                subprocess.call(shlex.split("rclone copyto " + src + dest + _dryRun))
            else:
                src  = '"' + remoteName + key + '" '
                dest = '"' + localRoot + '/' + key + '_REMOTE' + '" '
                logging.warning (printMsg ("*****", "  Changed in both local and remote", key))
                logging.warning (printMsg ("REMOTE", "  Copying to local", dest))
                subprocess.call(shlex.split("rclone copyto " + src + dest + _dryRun))
                # Rename local
                src  = '"' + localRoot + '/' + key + '" '
                dest = '"' + localRoot + '/' + key + '_LOCAL' + '" '
                logging.warning (printMsg ("LOCAL", "  Renaming local copy", dest))
                subprocess.call(shlex.split("rclone copyto " + src + dest + _dryRun))
             # else handler:  If also local new and not matching then create _REMOTE and _LOCAL versions

        if remoteDeltas[key]['newer']:
            #logging.info (printMsg ("REMOTE", "  Newer file", key))
            if key not in localDeltas:
                src  = '"' + remoteName + key + '" '
                dest = '"' + localRoot + '/' + key + '" '
                logging.info (printMsg ("REMOTE", "  Copying to local", dest))
                subprocess.call(shlex.split("rclone copyto " + src + dest + _dryRun))
            else:
                src  = '"' + remoteName + key + '" '
                dest = '"' + localRoot + '/' + key + '_REMOTE' + '" '
                logging.warning (printMsg ("*****", "  Changed in both local and remote", key))
                logging.warning (printMsg ("REMOTE", "  Copying to local", dest))
                subprocess.call(shlex.split("rclone copyto " + src + dest + _dryRun))
                # Also rename the local to _LOCAL

        if remoteDeltas[key]['deleted']:
            #logging.info (printMsg ("REMOTE", "  File was deleted", key))
            if key not in localDeltas:
                if key in localNow:
                    src  = '"' + localRoot + '/' + key + '" '
                    logging.info (printMsg ("LOCAL", "  Deleting file", src))
                    subprocess.call(shlex.split("rclone delete " + src + _dryRun))
            else:  # Changed locally too
                if key in localNow:
                    src  = '"' + localRoot + '/' + key + '" '
                    dest = '"' + localRoot + '/' + key + '_LOCAL' + '" '
                    logging.warning (printMsg ("*****", "  Also changed locally", key))
                    logging.warning (printMsg ("LOCAL", "  Renaming local", dest))
                    subprocess.call(shlex.split("rclone moveto " + src + dest + _dryRun))

    for key in localDeltas:
        if localDeltas[key]['deleted']:
            if (key in remoteDeltas) and (key in remoteNow):
                src  = '"' + remoteName + key + '"'
                dest = '"' + localRoot + '/' + key + '_REMOTE' + '"'
                logging.warning (printMsg ("*****", "  Deleted locally and also changed remotely", key))
                logging.warning (printMsg ("REMOTE", "  Copying to local", dest))
                subprocess.call(shlex.split("rclone copyto " + src + dest + _dryRun))


    # ***** Sync LOCAL changes to REMOTE ***** 
    if len(remoteDeltas) == 0 and len(localDeltas) == 0 and not firstSync:
        logging.info (">>>>> No changes on Local - Skipping sync from Local to Remote")
    else:
        logging.info (">>>>> Synching Local to Remote")
        if verbose:  syncVerbosity = '--verbose '
        else:        syncVerbosity = ' '
        switches = ' ' #'--ignore-size '
        subprocess.call(shlex.split("rclone sync " + localRootSP + remoteNameSP + syncVerbosity + switches + excludes + _dryRun))
        subprocess.call(shlex.split("rclone rmdirs " + remoteNameSP + _dryRun))
        subprocess.call(shlex.split("rclone rmdirs " + localRootSP + _dryRun))


    # ***** Clean up *****
    logging.info (">>>>> Refreshing Local and Remote lsl files")
    os.remove(remoteListFileNew)
    os.remove(localListFileNew)
    with open(localListFile, "w") as of:
        subprocess.call(shlex.split("rclone lsl " + localRootSP + excludes), stdout=of)
    with open(remoteListFile, "w") as of:
        subprocess.call(shlex.split("rclone lsl " + remoteNameSP + excludes), stdout=of)



def printMsg (locale, msg, key=''):
    return "{:9}{:35} - {}".format(locale, msg, key)


lineFormat = re.compile('\s*([0-9]+) ([\d\-]+) ([\d:]+).([\d]+) (.*)')

def loadList (infile):
    # Format ex:
    #  3009805 2013-09-16 04:13:50.000000000 12 - Wait.mp3
    #   541087 2017-06-19 21:23:28.610000000 DSC02478.JPG
    #    size  <----- datetime (epoch) ----> key

    d = {}
    with open(infile, 'r') as f:
        for line in f:
            out = lineFormat.match(line)
            if out:
                size = out.group(1)
                date = out.group(2)
                _time = out.group(3)
                microsec = out.group(4)
                date_time = time.mktime(datetime.strptime(date + ' ' + _time, '%Y-%m-%d %H:%M:%S').timetuple()) + float('.'+ microsec)
                filename = out.group(5)
                d[filename] = {'size': size, 'datetime': date_time}
            else:
                logging.warning ("Something wrong with this line in {}:\n   <{}>".format(infile, line))

    return collections.OrderedDict(sorted(d.items()))       # return a sorted list


lockfile = "/tmp/RCloneSync_LOCK"
def requestLock (caller):
    for xx in range(5):
        if os.path.exists(lockfile):
            with open(lockfile) as fd:
                lockedBy = fd.read()
                logging.debug ("{}.  Waiting a sec.".format(lockedBy[:-1]))   # remove the \n
            time.sleep (1)
        else:  
            with open(lockfile, 'w') as fd:
                fd.write("Locked by {} at {}\n".format(caller, time.asctime(time.localtime())))
                logging.debug ("LOCKed by {} at {}.".format(caller, time.asctime(time.localtime())))
            return 0
    logging.warning ("Timed out waiting for LOCK file to be cleared.  {}".format(lockedBy))
    return -1
        

def releaseLock (caller):
    if os.path.exists(lockfile):
        with open(lockfile) as fd:
            lockedBy = fd.read()
            logging.debug ("Removed lock file:  {}.".format(lockedBy))
        os.remove(lockfile)
        return 0
    else:
        logging.warning ("<{}> attempted to remove /tmp/LOCK but the file does not exist.".format(caller))
        return -1
        


if __name__ == '__main__':

    logging.warning ("***** BiDirectional Sync for Cloud Services using RClone *****")

    try:
        clouds = subprocess.check_output(['rclone', 'listremotes'])
    except:
        logging.error (printMsg ("ERROR*****", "rclone not installed?", ''))
        exit()
    clouds = clouds.split()

    parser = argparse.ArgumentParser(description="***** BiDirectional Sync for Cloud Services using RClone *****")
    parser.add_argument('Cloud',        help="Name of remote cloud service", choices=clouds)
    parser.add_argument('LocalRoot',    help="Path to local root", default=None)
    parser.add_argument('--FirstSync',  help="First run setup.  WARNING: Local files may overwrite Remote versions", action='store_true')
    parser.add_argument('--ExcludeListFile', help="File containing rclone file/path exclusions (Needed for Dropbox)", default=None)
    parser.add_argument('--Verbose',    help="Event logging with per-file details (Python INFO level - default is WARNING level)", action='store_true')
    parser.add_argument('--DryRun',     help="Go thru the motions - No files are copied/deleted", action='store_true')
    args = parser.parse_args()

    remoteName   = args.Cloud
    remoteNameSP = remoteName + ' '           # Space on end added to keep the subprocess call code clean
    localRoot    = args.LocalRoot
    localRootSP  = args.LocalRoot + ' '
    firstSync    = args.FirstSync
    verbose      = args.Verbose
    exclusions   = args.ExcludeListFile
    dryRun       = args.DryRun

    if verbose:
        logging.getLogger().setLevel(logging.INFO)      # Log each file transaction
    else:
        logging.getLogger().setLevel(logging.WARNING)   # Log only unusual events

    if requestLock (sys.argv) == 0:
        if main():
            logging.error ('***** Error abort *****')
        releaseLock (sys.argv)
    else:  logging.warning ("Prior lock file in place.  Aborting.")
    logging.warning (">>>>> All done.\n\n")
