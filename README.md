# RCloneSync
Python cloud sync utility using rclone

Rclone provides a programmatic building block interface for transferring files between a cloud service provider and your local filesystem (actually a lot of functionality), but rclone does not provide a turnkey bidirectional sync capability.  RCloneSync.py provides a bidirectional sync solution.

I use RCloneSync on a Centos 7 box to sync both Dropbox and Google Drive to a local disk which is Samba shared on my LAN.   I run it as a Cron job every 30 minutes, or on-demand from the command line.  RCloneSync was developed and debugged for Google Drive and Dropbox (not tested on other services).  

	[RCloneSyncWD]$ ./RCloneSync.py --help
	2017-08-06 21:52:03,520/WARNING:  ***** BiDirectional Sync for Cloud Services using RClone *****
	usage: RCloneSync.py [-h] [--FirstSync] [--ExcludeListFile EXCLUDELISTFILE]
	                     [--Verbose] [--DryRun]
	                     {Dropbox:,GDrive:} LocalRoot
	
	***** BiDirectional Sync for Cloud Services using RClone *****
	
	positional arguments:
	  {Dropbox:,GDrive:}    Name of remote cloud service
	  LocalRoot             Path to local root
	
	optional arguments:
	  -h, --help            show this help message and exit
	  --FirstSync           First run setup. WARNING: Local files may overwrite
	                        Remote versions
	  --ExcludeListFile EXCLUDELISTFILE
	                        File containing rclone file/path exclusions (Needed
	                        for Dropbox)
	  --Verbose             Event logging with per-file details (Python INFO level
	                        - default is WARNING level)
	  --DryRun              Go thru the motions - No files are copied/deleted
	
Key behaviors / operations
  
  Keeps an rclone lsl file list of the Local and Remote systems.  On each run, checks for deltas on Local and Remote.
  
  Applies Remote deltas to the Local filesystem, then rclone syncs the Local to the Remote file system.
  
  Handles change conflicts nondestructively by creating _LOCAL and _REMOTE file versions.
	
  Somewhat fail safe - Lock file prevents multiple simultaneous runs when taking a while, and file access health check using RCLONE_TEST files.

Typical run log:

/RCloneSync.py Dropbox:  /mnt/raid1/share/public/DBox/Dropbox --ExcludeListFile /home/xxx/RCloneSyncWD/Dropbox_Excludes --Verbose

2017-08-06 21:25:14,023/WARNING:  ***** BiDirectional Sync for Cloud Services using RClone *****

2017-08-06 21:25:14,031/INFO:  >>>>> Checking rclone Local and Remote access health

2017-08-06 21:25:15,433/INFO:  >>>>> Generating Local and Remote lists

2017-08-06 21:25:16,492/INFO:  LOCAL    Checking for Diffs                  - /mnt/raid1/share/public/DBox/Dropbox

2017-08-06 21:25:16,493/INFO:  LOCAL      File was deleted                  - SW1/python/RCloneSync/rclone - Copy.txt

2017-08-06 21:25:16,493/INFO:  LOCAL      File is new                       - SW1/python/RCloneSync/rclone.test

2017-08-06 21:25:16,493/WARNING:       2 file change(s) on the Local system /mnt/raid1/share/public/DBox/Dropbox

2017-08-06 21:25:16,493/INFO:  REMOTE   Checking for Diffs                  - Dropbox:

2017-08-06 21:25:16,493/INFO:  REMOTE     File was deleted                  - Exchange/20170803_100011 (Small).jpg

2017-08-06 21:25:16,493/INFO:  REMOTE     File was deleted                  - Exchange/20170803_105125 (Small).jpg

2017-08-06 21:25:16,494/INFO:  REMOTE     File is new                       - Exchange/20170803_100011 test.jpg

2017-08-06 21:25:16,494/WARNING:       3 file change(s) on Dropbox:

2017-08-06 21:25:16,494/INFO:  >>>>> Applying changes on Remote to Local

2017-08-06 21:25:16,494/INFO:  LOCAL      Deleting file                     - 
"/mnt/raid1/share/public/DBox/Dropbox/Exchange/20170803_100011 (Small).jpg" 

2017-08-06 21:25:16,500/INFO:  REMOTE     Copying to local                  - "/mnt/raid1/share/public/DBox/Dropbox/Exchange/20170803_100011 test.jpg" 

2017-08-06 21:25:17,604/INFO:  LOCAL      Deleting file                     - "/mnt/raid1/share/public/DBox/Dropbox/Exchange/20170803_105125 (Small).jpg" 

2017-08-06 21:25:17,613/INFO:  >>>>> Synching Local to Remote

2017/08/06 21:25:17 INFO  : Dropbox root '': Modify window not supported

2017/08/06 21:25:19 INFO  : Dropbox root '': Waiting for checks to finish

2017/08/06 21:25:19 INFO  : Dropbox root '': Waiting for transfers to finish

2017/08/06 21:25:20 INFO  : SW1/python/RCloneSync/rclone.test: Copied (new)

2017/08/06 21:25:20 INFO  : Waiting for deletions to finish

2017/08/06 21:25:20 INFO  : SW1/python/RCloneSync/rclone - Copy.txt: Deleted

2017/08/06 21:25:20 INFO  : 

Transferred:    356 Bytes (109 Bytes/s)

Errors:                 0

Checks:               683

Transferred:            1

Elapsed time:        3.2s

2017-08-06 21:25:22,059/INFO:  >>>>> Refreshing Local and Remote lsl files

2017-08-06 21:25:23,215/WARNING:  >>>>> All done.

A basic communications integrity check is implemented using check files named RCLONE_TEST.  One or more of these files must be placed in the Local and Remote/cloud file system in matching locations.  One way to do so is to create the files on the local system and then do a manual rclone copy or rclone sync to the remote system.  

The --ExcludeListFile optional param is needed for Drobox, which has a set of file names that cannot be copied to Dropbox.  The provided exclude file may be used with Dropbox.  Note the usage caution within the file.

