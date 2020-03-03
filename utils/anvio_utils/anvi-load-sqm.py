#!/usr/bin/env python3


"""
-------------------------------------------------------------------------------
Part of the SqueezeMeta distribution. 27-05-2019 Original version,
                            (c) Natalia Garcia-Garcia, CNB-CSIC.
                            
Load results from SQM in anvi'o.
Run this script in the project directory:
    - Run sqm2anvio.pl in case there is none. 
    It contains:
        - Text files: contigs, genes, functions, taxonomy (contigs and genes) and bins (optional).
        - bam: directory with bam files. Bam files' names must finish with '-RAW.bam'.
    
USAGE: anvi-load-sqm.py [-h] -p PROJECT -o OUTPUT [--num-threads NUM_THREADS]
                        [--run-HMMS] [--min-contig-length MIN_CONTIG_LENGTH]
                        [--min-mean-coverage MIN_MEAN_COVERAGE]
                        [--skip-SNV-profiling] [--profile-SCVs]


       -p PROJECT, --project PROJECT          Name of the SQM project. E.g. Hadza16 (REQUIRED)
       -o OUTPUT                              Path to the output directory (REQUIRED)
       --num-threads         NUM_THREADS      Number of threads
       --run-HMMS                             Run anvi-run-hmms command from anvi'o for identifying single-copy core genes
       --min-contig-length  MIN_CONTIG_LENGTH Minimum length of contigs
       --min-mean-coverage  MIN_MEAN_COVERAGE Minimum mean coverage for contigs
       --skip-SNV-profiling                   To skip the profiling of SNV
       --profile-SCVs                         Perform characterization of codon frequencies in genes
       --run-scg-taxonomy                     Just for anvio 6. Perform taxonomic assignation of single-copy core genes
                                            based on The Genome Taxonomy Database (GTDB) Parks, D. et al. (2018) doi:10.1038/nbt.4229.
                                              Note that if it is the first time you use it in anvio 6, it would be necessary to run the
                                              anvi-setup-scg-databases to set up the database
                                              (more info: http://merenlab.org/2019/10/08/anvio-scg-taxonomy/)
 
ABOUT ANVI'O:
    - Anvi'o is an advanced analysis and visualization platform for 'omics data.
    - Citation: Eren AM, Ozcan E, Quince C, Vineis JH, Morrison HG, Sogin ML, Delmont TO. (2015)
                Anvi'o: an advanced analysis and visualization platform for 'omics data. PeerJ 3:e1319
    - This script runs a set of pre-defined commands to create an anvio database from the results generated by sqm2anvio.pl.
    - If you want to explore ways to manually create the database, and other cool stuff that you can do with anvio
    for information, tutorials and more details (http://merenlab.org/software/anvio/).

-------------------------------------------------------------------------------
"""

import subprocess
import os
import argparse
import sqlite3
from collections import defaultdict
from glob import glob
import os
import shutil
import sys
from os.path import abspath, dirname, realpath
try:
    import anvio
except ModuleNotFoundError:
    raise Exception('Anvi\'o has not been detected. Are you sure that it has been activated?')


# Describe functions

#FUN: Parser input data
def parse_arguments():
    """Parse the command line arguments and return an object containing them"""
    # Required
    general = argparse.ArgumentParser(description='Process input files')
    general.add_argument( '-p','--project',type=str, required=True, help='Name of the SQM project. E.g. Hadza16')
    # Optional:
    general.add_argument('-o','--output', required=True, help='Path to the output directory')
    general.add_argument('--num-threads', default=12, type=int, help='Number of threads')
    general.add_argument('--run-HMMS', action = 'store_true', help='Run anvi-run-hmms command from anvi\'o for identifying single-copy core genes')
    general.add_argument('--run-scg-taxonomy', action = 'store_true', help='Run anvi-run-scg-taxonomy command from anvi\'o for identifying taxonomy of single-copy core genes.'+'\n'+ 'This flag is available for version anvio 6, not anvio 5.'+'\n'+'Note that if it is the first time you use it, it would be necessary to run the command anvi-setup-scg-databases to set up the database (more info: http://merenlab.org/2019/10/08/anvio-scg-taxonomy/')
    general.add_argument('--min-contig-length', default=0, type=int, help='Minimum length of contigs')  
    general.add_argument('--min-mean-coverage', default=0, type=int, help='Minimum mean coverage for contigs')
    general.add_argument('--skip-SNV-profiling', action='store_true', help='To skip the profiling of SNV')
    general.add_argument('--profile-SCVs', action='store_true', help='Perform characterization of codon frequencies in genes')
    args = general.parse_args()
    return(args)

#FUN: Run and check whether the subprocess worked well
def run_command(command):# run_command
    """Run the command and check the success of the subprocess. Return exit if it went wrong"""
    exitcode=subprocess.call(map(str,command)) 
    if exitcode != 0:
        print('There must be some problem with "{}".\nIt\'s better to stop and check it'.format(' '.join(command)))
        exit(-1)

#FUNS:
def check_sqm2anvio(project):
    """ Check if sqm2anvio contains all the files """
    files = []
    sqm2anvioPath = abspath('{}/results/sqm2anvio'.format(project))
    print(sqm2anvioPath)
    for f in ['_anvio_contigs', '_anvio_genes', '_anvio_functions','_anvio_taxonomy','_anvio_contig_taxonomy']:
        globList = glob('{}/*{}.txt'.format(sqm2anvioPath,f)) #recover names of files that are arguments for anvio
        if not globList:
            print('The file ended in \'{}.txt\' seems not to exist. This file should have been generated by sqm2qnvio.pl . If it is not present, remove the directory and this script will create a new one'.format(f))
            exit(-1)
        elif len(globList) > 1:
            print('There seems to be more than one file ended in \'{}.txt\'. Are you trying to trick us?'.format(f))
            exit(-1)
        elif not os.path.isfile(globList[0]):
            print('{} is not a file! We really thought this would never happen!'.format(globlist[0]))
            exit(-1)
        else:
            files.append(globList[0])
        
    if not os.path.isdir('{}/bam'.format(sqm2anvioPath)):
        print('There is not a bam directory. It should have been generated by sqm2anvio.pl . If it is not present, remove the directory and this script will create a new one')
        exit(-1)
    else: files.append('bam')           
    return files

def load_taxonomy(output, tax_contigs, tax_genes):
    """ Load contigs & genes taxonomy using sqlite3 """
    conn = sqlite3.connect('{}/CONTIGS.db'.format(output))
    c = conn.cursor()
    
    ## Execute selection of splits
    c.execute('SELECT split FROM splits_basic_info')
    splits = [s[0] for s in c.fetchall()]
    
    ## Dictionary: {contig:tax }
    with open(tax_contigs,'r') as infile:
        contig_tax = {}
        infile.readline() # burn headers
        contig_tax = dict([line.rstrip('\n').split('\t',1) for line in infile]) 
    
    split_tax = {s: contig_tax[s.split('_split_')[0]] for s in splits}
    
    ## Dictionary {gen:tax}
    with open(tax_genes,'r') as infile2:
        gen_tax = {}
        infile2.readline() # burn headers
        gen_tax = dict([line.rstrip('\n').split('\t',1) for line in infile2])
    
    ## Join all the possible taxonomy combinations: from genes + contigs # could happen that genes have different taxonomy annotations than in contigs are not consiodered due to the consensus procedure.
    taxa = set( list(split_tax.values()) + list(gen_tax.values()) )
    taxon_names = {taxon:i+1 for i,taxon in enumerate(taxa)}
    
    for t in taxon_names.keys():            
        stmt = "INSERT INTO taxon_names (taxon_id, t_phylum, t_class, t_order, t_family, t_genus, t_species) VALUES (?,?,?,?,?,?,?);"
        tax_list = t.split('\t')[1:len(t)]
        values = [taxon_names[t]]+tax_list #remove superkingdom
        c.execute(stmt,values)
        
    #splits_taxonomy: split \t ids de la taxonomy   
    for s in split_tax:
        stmt = "INSERT INTO splits_taxonomy (split, taxon_id) VALUES (?,?);"
        values = [s,taxon_names[split_tax[s]]]
        c.execute(stmt,values)
        
    #genes_taxonomy: gen \t ids de la taxonomy   
    for gen in gen_tax:
        stmt = "INSERT INTO genes_taxonomy (gene_callers_id, taxon_id) VALUES (?,?);"
        values = [gen,taxon_names[gen_tax[gen]]]
        c.execute(stmt,values)
    #Close DB saving changes    
    conn.commit()

def create_contigsDB(project, contigs, genes, functions, tax_genes, tax_contigs, output, run_HMMS, num_threads, run_scg_taxonomy, version):
    """ Run anvio commands """
    #! Start running anvio, independently of number of samples. Make complete CONTIGS.db
    print('Preparing contigs database: loading contigs, genes, functions and taxonomy!')
    
    # Load contigs & genes with some parameters from anvio
    command = ['anvi-gen-contigs-database', '-f', contigs,'-n', project,'-o', '{}/CONTIGS.db'.format(output),  '--external-gene-call', genes,'--ignore-internal-stop-codons']
    run_command(command)
    print('Contigs database is CONTIGS.db. Contigs and genes have been loaded')
    
    # Run if it's required the HMMS option from anvio
    if run_HMMS:
        print('Running HMMS to detect SCGs')
        command = ['anvi-run-hmms', '-c', '{}/CONTIGS.db'.format(output), '--num-threads' , num_threads]
        run_command(command)
    
    # Run scg-taxonomy option from anvio (NEW FOR ANVIO >= 6)
    if run_scg_taxonomy and version >= 6:
        #command = ['anvi-setup-scg-databases', '-T', '4'] # ONLY NEEDED THE FIRST TIME
        #run_command(command)
        if not run_HMMS:
            print('Running HMMs (It is necessary to run run_scg_taxonomy)')
            command = ['anvi-run-hmms', '-c', '{}/CONTIGS.db'.format(output), '--num-threads' , num_threads]
            run_command(command)
        command = ['anvi-run-scg-taxonomy', '-c', '{}/CONTIGS.db'.format(output), '--num-parallel-processes', '3', '--num-threads', num_threads]
        run_command(command)
    elif version < 6:
        print('run-scg-taxonomy option is not available in this version')
    
    # Load functions    
    command = ['anvi-import-functions', '-c', '{}/CONTIGS.db'.format(output), '-i' , functions]
    run_command(command)
    print('Functions have been loaded')
    
    # Load taxonomy
    load_taxonomy(output, tax_contigs, tax_genes)
    print('Taxonomy has been loaded')

def create_profileDB(project, output, min_contig_length, min_mean_coverage, num_threads, skip_SNV_profiling, profile_SCVs, version):
    """ Make profiles.db. Load bam files, important: distinguish number of samples """
    print('Loading bam files')
    samples = [f for f in os.listdir('{}/results/sqm2anvio/bam'.format(project)) if f.endswith('-RAW.bam')]
    
    for f in samples:
        #print(f)
        print('Processing {}'.format(f))
        f_in = project + '/results/sqm2anvio/bam/' + f
        f_out = f_in.replace('-RAW','')
        # Order & Index bam file
        command = ['anvi-init-bam', f_in, '-o', f_out]
        run_command(command)
        #print(f_out)
        print('Profiling {}'.format(f))
        # Profile bam file

        profile_name = '{}/{}_temp'.format(output,f.replace('-RAW.bam',''))
        command_base = ['anvi-profile','-i',f_out, '-o', profile_name, '-c', '{}/CONTIGS.db'.format(output), '--min-contig-length', min_contig_length ,'--min-mean-coverage', min_mean_coverage,'--num-threads' , num_threads,'--skip-hierarchical-clustering']
        if skip_SNV_profiling:
            command_base.append('--skip-SNV-profiling')
        if profile_SCVs:
            command_base.append('--profile-SCVs')
        run_command(command_base)
        print('Removing sort and index bam file')
        command = ['rm',f_out,'{}.bai'.format(f_out) ]
        run_command(command)
        
    
    profiles_names = ['{}/{}_temp'.format(output, f.replace('-RAW.bam','')) for f in samples]
    if not samples:
        # Make a blank profile
        profile_name ='{}/temp'.format(output)
        command = ['anvi-profile', '-o', profile_name, '-c', '{}/CONTIGS.db'.format(output), '--blank-profile','-S','Blank','--min-contig-length', min_contig_length ,'--num-threads' , num_threads,'--skip-hierarchical-clustering']
        run_command(command)

    elif len(samples) == 1: #Remove flag --skip-concoct-binning (NEW FOR ANVIO 6)
        # A single profile contains the abundance information inside binary blobs in the AUXILIARY database, which scares us.
        # In order to get the abundance information as plain text inside the PROFILE database, we run anvi-merge with the same sample twice.
        # This seems to work fine. However, if you are an anvi'o developer, please excuse us for being lazy and hacky ^^'
        command = ['anvi-merge', '{}/PROFILE.db'.format(profile_name),  '{}/PROFILE.db'.format(profile_name),'-c','{}/CONTIGS.db'.format(output),'-o','{}/temp'.format(output),'--skip-hierarchical-clustering']
        if version < 6:# NEW
            command.append('--skip-concoct-binning') #NEW
        run_command(command)
                           
    else: #Remove flag --skip-concoct-binning (NEW FOR ANVIO 6)
        # If there are 2 or more samples: Merge profiles.db
        print('Merging profile databases')
        profile_dir = ['{}/PROFILE.db'.format(p) for p in profiles_names]
        print('These are the profiles databases {} that will be merged'.format(profile_dir))
        command = ['anvi-merge'] + profile_dir + ['-c','{}/CONTIGS.db'.format(output),'-o','{}/temp'.format(output),'--skip-hierarchical-clustering'] ## ADD SAMPLE-NAME??
        if version < 6:# NEW
            command.append('--skip-concoct-binning') #NEW
        run_command(command)

def load_bins(project, output):
    """ Load bins collection """
    if len(glob('{}/results/sqm2anvio/*anvio_bins.txt'.format(project)))==1:
        if os.path.isfile(glob('{}/results/sqm2anvio/*anvio_bins.txt'.format(project))[0]):
            print('Loading DAS collection')
            command = ['anvi-import-collection',glob('{}/results/sqm2anvio/*anvio_bins.txt'.format(project))[0],'-c','{}/CONTIGS.db'.format(output),'-p', '{}/temp/PROFILE.db'.format(output), '-C', 'DAS', '--contigs-mode']
            run_command(command)
            print('DAS collection is loaded')
        else: print('Your bins file is not a file! We really thought this would never happen!')
    else: 
        print('There is no bins collection or there are more than two! Skipping...')



#FUN: Main
def main(args):
    """Get things done"""
    
    print('------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------')
    print('Loading results from SQM in anvi\'o.\nAnvi\'o is an advanced analysis and visualization platform for \'omics data.',
          'Citation: Eren AM, Ozcan E, Quince C, Vineis JH, Morrison HG, Sogin ML, Delmont TO. (2015) Anvi\'o: an advanced analysis and visualization platform for \'omics data. PeerJ 3:e1319',
          'This script calls to sqm2anvio.pl and then runs a set of pre-defined commands to create an anvio database.',
          'If you want to explore ways to manually create the database, and other cool stuff that you can do with anvi\'o',
          'please consider checking the anvi\'o project page for information, tutorials and more details (http://merenlab.org/software/anvio/).', sep='\n')
    print('------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------')

    utils_home = abspath(dirname(realpath(__file__)))
    scriptlaunch = utils_home + ' '.join(sys.argv)
    # Create output dir
    if args.output != '.':
        if os.path.exists(args.output):
            print('There is a previous {}. Please, remove it or choose other name for the output'.format(args.output))
            exit(-1)
        else:
            subprocess.call(['mkdir', args.output])
    
    # NEW: Find out anvio version:
    version = float(anvio.__version__)
    
    #! FIRST: Run sqm2anvio.pl if it not in the project
    if os.path.isdir('{}/results/sqm2anvio'.format(args.project)):
        print('There is a sqm2anvio directory that we hope to contain your latest results, if it is not the case, remove it and this script will create a new one with your latest results')
        contigs, genes, functions, tax_genes, tax_contigs, bams = check_sqm2anvio(args.project)
    else:
        print('{}/results/sqm2anvio does not exist'.format(args.project)) ###############333 CREATE!!!!!!
        print('Create sqm2anvio directory with all the input files for anvi\'o')
        command = ['{}/sqm2anvio.pl'.format(utils_home), args.project, '{}/results/sqm2anvio'.format(args.project)]
        run_command(command)
        contigs, genes, functions, tax_genes, tax_contigs, bams = check_sqm2anvio(args.project)
    
    if os.path.abspath(args.output) != os.path.abspath(args.project):
        # Ignore this copy if someone is writing the results to the input folder
        command = ['cp',tax_contigs, args.output]
        run_command(command)
    
    # Create CONTIGS.db
    create_contigsDB(args.project, contigs, genes, functions, tax_genes, tax_contigs, args.output, args.run_HMMS, args.num_threads, args.run_scg_taxonomy, version)
    #Create PROFILE.db
    create_profileDB(args.project, args.output, args.min_contig_length, args.min_mean_coverage, args.num_threads, args.skip_SNV_profiling, args.profile_SCVs, version)                
    #Load Bin collection
    load_bins(args.project, args.output)    

    # Move PROFILE.db & AUXILIARY-DATA.db to the same level than CONTIGS.db
    shutil.move('{}/temp/PROFILE.db'.format(args.output),'{}/PROFILE.db'.format(args.output))
    shutil.move('{}/temp/AUXILIARY-DATA.db'.format(args.output),'{}/AUXILIARY-DATA.db'.format(args.output))
    shutil.move('{}/temp/RUNLOG.txt'.format(args.output),'{}/RUNLOG.txt'.format(args.output))
    # Remove temp directory & individual profiles directories
    for d in os.listdir(args.output):
        if d.endswith('temp'):
            shutil.rmtree('{}/{}'.format(args.output,d))
    print('Your data has been loaded. If you want to explore them you can use anvi-filter-sqm.py :)')
    with open('{}/anvi-load-sqm.log'.format(args.output), 'w') as logfile:
        logfile.write('Your data has been loaded into CONTIGS.db & PROFILE.db. If you want to explore them you can use anvi-filter-sqm.py\n{}'.format(scriptlaunch))

################################################################################################################
    
if __name__ == '__main__':
    main(parse_arguments())