grep 'CID-0[0-2]:FPC-0[0-9]:PIC-0[0-9]:THREAD_ID-[0-9][0-9]:' -o $1  | sort | uniq > thd_id

for i in `cat thd_id` ; do grep $i $1 >> $2; done

