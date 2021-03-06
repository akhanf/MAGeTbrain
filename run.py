#!/usr/bin/env python
import argparse
import os
import shutil
import subprocess
from glob import glob
import errno

__version__ = open(os.path.join('/version')).read()


def symlink_force(target, link_name):
    try:
        os.symlink(target, link_name)
    except OSError as e:
        if e.errno == errno.EEXIST:
            os.remove(link_name)
            os.symlink(target, link_name)
        else:
            raise e


def run(command, env={}):
    merged_env = os.environ
    merged_env.update(env)
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, shell=True,
                               env=merged_env)
    while True:
        line = process.stdout.readline()
        line = str(line, 'utf-8')[:-1]
        print(line)
        if line == '' and process.poll() is not None:
            break
    if process.returncode != 0:
        raise Exception("Non zero return code: {0}".format(process.returncode))


parser = argparse.ArgumentParser(
    description='MAGeTbrain BIDS App entrypoint script.')
parser.add_argument('bids_dir', help='The directory with the input dataset '
                    'formatted according to the BIDS standard.')
parser.add_argument('output_dir', help='The directory where the output files '
                    'should be stored. When you are running group level analysis '
                    'this folder must be prepopulated with the results of the'
                    'participant level analysis.')
parser.add_argument('analysis_level', help='Level of the analysis that will be performed. '
                    'Multiple participant level analyses can be run independently '
                    '(in parallel) using the same output_dir. '
                    'In MAGeTbrain parlance, participant1 = template stage, partipant2 = subject stage '
                    'group = resample + vote + qc stage. '
                    'The proper order is participant1, participant2, group',
                    choices=['participant1', 'participant2', 'group'])
parser.add_argument('--participant_label', help='The label(s) of the participant(s) that should be analyzed. The label '
                   'corresponds to sub-<participant_label> from the BIDS spec '
                   '(so it does not include "sub-"). If this parameter is not '
                   'provided all subjects should be analyzed. Multiple '
                   'participants can be specified with a space separated list.',
                   nargs="+")
parser.add_argument('--segmentation_type', help='The segmentation label type to be used.'
                    ' colin27-subcortical, since it is on a different atlas, is not included '
                    'in the all setting and must be run seperately',
                    choices=['amygdala', 'cerebellum',
                        'hippocampus-whitematter', 'colin27-subcortical', 'all'],
                    default='all')
parser.add_argument('-v', '--version', action='version',
                    version='MAGeTbrain version {}'.format(__version__))
parser.add_argument('--n_cpus', help='Number of CPUs/cores available to use.',
                   default=1, type=int)
parser.add_argument('--fast', help='Use faster (less accurate) registration calls',
                   action='store_true')
parser.add_argument('--label-masking', help='Use the input labels as registration masks to reduce computation '
                    'and (possibily) improve registration',
                   action='store_true')
parser.add_argument('--no-cleanup', help='Do no cleanup intermediate files after group phase',
                   action='store_true')

args = parser.parse_args()

# Check validity of bids dataset
run('bids-validator {0}'.format(args.bids_dir))

# Setup magetbrain inputs
os.chdir(args.output_dir)
run('mb.sh -- init')

#Link in either colin or the big 5 atlases
if args.segmentation_type != 'colin27-subcortical':
    atlases = glob("/opt/atlases-nifti/brains_t1_nifti/*nii.gz")
    for atlas in atlases:
        shutil.copy(
            atlas, '{0}/input/atlas/{1}'.format(args.output_dir, os.path.basename(atlas)))
else:
    shutil.copy('/opt/atlases-nifti/colin/colin27_t1_tal_lin.nii',
                  '{0}/input/atlas/colin27_t1.nii'.format(args.output_dir))

#Link in the labels selected
if args.segmentation_type == 'amygdala':
    labels = glob('/opt/atlases-nifti/amygdala/labels/*.nii.gz')
    for label in labels:
        shutil.copy(label, '{0}/input/atlas/{1}_amygdala.nii.gz'.format(
            args.output_dir, os.path.splitext(os.path.splitext(os.path.basename(label))[0])[0][0:-1]))
elif args.segmentation_type == 'cerebellum':
    labels = glob('/opt/atlases-nifti/cerebellum/labels/*.nii.gz')
    for label in labels:
        shutil.copy(label, '{0}/input/atlas/{1}_cerebellum.nii.gz'.format(
            args.output_dir, os.path.splitext(os.path.splitext(os.path.basename(label))[0])[0][0:-1]))
elif args.segmentation_type == 'hippocampus-whitematter':
    labels = glob('/opt/atlases-nifti/hippocampus-whitematter/labels/*.nii.gz')
    for label in labels:
        shutil.copy(label, '{0}/input/atlas/{1}_hcwm.nii.gz'.format(
            args.output_dir, os.path.splitext(os.path.splitext(os.path.basename(label))[0])[0][0:-1]))
elif args.segmentation_type == 'all':
    labels = glob('/opt/atlases-nifti/amygdala/labels/*.nii.gz')
    for label in labels:
        shutil.copy(label, '{0}/input/atlas/{1}_amygdala.nii.gz'.format(
            args.output_dir, os.path.splitext(os.path.splitext(os.path.basename(label))[0])[0][0:-1]))

    labels = glob('/opt/atlases-nifti/cerebellum/labels/*.nii.gz')
    for label in labels:
        shutil.copy(label, '{0}/input/atlas/{1}_cerebellum.nii.gz'.format(
            args.output_dir, os.path.splitext(os.path.splitext(os.path.basename(label))[0])[0][0:-1]))

    labels = glob('/opt/atlases-nifti/hippocampus-whitematter/labels/*.nii.gz')
    for label in labels:
        shutil.copy(label, '{0}/input/atlas/{1}_hcwm.nii.gz'.format(
            args.output_dir, os.path.splitext(os.path.splitext(os.path.basename(label))[0])[0][0:-1]))
elif args.segmentation_type == 'colin27-subcortical':
    shutil.copy('/opt/atlases-nifti/colin27-subcortical/labels/thalamus-globus_pallidus-striatum.nii.gz',
                  '{0}/input/atlas/colin27_label_subcortical.nii.gz'.format(args.output_dir))

#Select subjects
subjects_to_analyze = []
# only for a subset of subjects
if args.participant_label:
    subjects_to_analyze = args.participant_label
# for all subjects
else:
    subject_dirs = glob(os.path.join(args.bids_dir, "sub-*"))
    subjects_to_analyze = [subject_dir.split(
        "-")[-1] for subject_dir in subject_dirs]

# running participant level (must be done after template)
if args.analysis_level == "participant2":
    T1_files = []
    for subject in subjects_to_analyze:
        T1_files.append(glob(os.path.join(args.bids_dir, "sub-{0}".format(subject),
                                         "anat", "*_T1w.nii*")) + glob(os.path.join(args.bids_dir, "sub-{0}".format(subject), "ses-*", "anat", "*_T1w.nii*")))
    subject_T1_list = []
    for subject_T1s in T1_files:
         for session in subject_T1s:
             subject_T1_list.append('/{0}/input/subject/{1}'.format(args.output_dir, os.path.basename(session)))
             shutil.copy(session, '/{0}/input/subject/{1}'.format(args.output_dir, os.path.basename(session)))
    cmd = "QBATCH_PPJ={0} QBATCH_CHUNKSIZE=1 QBATCH_CORES=1 mb.sh {1} {2} -s ".format(args.n_cpus, args.fast and "--reg-command mb_register_fast.sh" or '',args.label_masking and '--label-masking' or '') + " ".join(subject_T1_list) + " -- subject"
    run(cmd)

# running template level preprocessing
elif args.analysis_level == "participant1":
    template_T1_files = []
    for subject in subjects_to_analyze:
        template_T1_files.append(glob(os.path.join(args.bids_dir, "sub-{0}".format(subject),
                                         "anat", "*_T1w.nii*")) + glob(os.path.join(args.bids_dir,"sub-{0}".format(subject),"ses-*","anat", "*_T1w.nii*")))
    # Only choose first item for each list, in case of longitudinal data
    # limit list to 21 subjects which is the standard max for MAGeTbrain templates
    template_T1_list = []
    if args.participant_label:
        for subject_file in template_T1_files:
            shutil.copy(subject_file[0], '/{0}/input/template/{1}'.format(args.output_dir, os.path.basename(subject_file[0])))
            template_T1_list.append('/{0}/input/template/{1}'.format(args.output_dir, os.path.basename(subject_file[0])))
    else:
        for subject_file in template_T1_files[0:20]:
            shutil.copy(subject_file[0], '/{0}/input/template/{1}'.format(args.output_dir, os.path.basename(subject_file[0])))
            template_T1_list.append('/{0}/input/template/{1}'.format(args.output_dir, os.path.basename(subject_file[0])))
    cmd = "QBATCH_PPJ={0} QBATCH_CHUNKSIZE=1 QBATCH_CORES=1 mb.sh {1} {2} -t ".format(args.n_cpus, args.fast and '--reg-command mb_register_fast.sh' or '',args.label_masking and '--label-masking' or '') + " ".join(template_T1_list) + " -- template"
    run(cmd)

elif args.analysis_level == "group":
    cmd = "QBATCH_PPJ={0} QBATCH_CHUNKSIZE=1 QBATCH_CORES=1 mb.sh".format(args.n_cpus) + " -- resample vote qc"
    run(cmd)
    if (not args.no_cleanup):
        run("rm -rf input")
        run("rm -rf output/transforms")
        run("rm -rf output/labels/candidates")
