"""Run the mni to bold transformation on an fmriprep output"""
import os

def get_parser():
    """Build parser object."""
    from argparse import ArgumentParser
    from argparse import RawTextHelpFormatter, RawDescriptionHelpFormatter

    parser = ArgumentParser(
        description="""NiWorkflows Utilities""", formatter_class=RawTextHelpFormatter
    )
    parser.add_argument("fmriprep_dir", action="store", help="fmriprep directory to pull scans from")
    parser.add_argument("out_path", action="store", help="the output directory")
    parser.add_argument('mni_image', action="store", help="mni template image to use")
    parser.add_argument('dseg_path', action="store", help="segmentation to use")

    parser.add_argument(
        '--n_dummy',
        action="store",
        help="number of dummy scans",
        type=int,
        default=4
    )
    parser.add_argument(
        "--omp-nthreads",
        action="store",
        type=int,
        default=os.cpu_count(),
        help="Number of CPUs available to individual processes",
    )
    parser.add_argument(
        "--mem-gb",
        action="store",
        type=int,
        default=1,
        help="Gigs of ram avialable"
    )

    return parser


# Get the grand mean std
def roi_grand_std(in_file, dseg_file, out_file=None):
    from nilearn import image as nli
    from nilearn._utils.niimg import _safe_get_data
    from nilearn._utils import check_niimg_4d
    import pandas as pd
    import os
    
    n_dummy=4
    if out_file is None:
        out_file = os.getcwd() + '/grand_std.csv'
    atlaslabels = nli.load_img(dseg_file).get_fdata()
    img_nii = check_niimg_4d(in_file, dtype="auto",)
    func_data = nli.load_img(img_nii).get_fdata()[:,:,:,n_dummy:]
    ntsteps = func_data.shape[-1]
    data = func_data[atlaslabels > 0].reshape(-1, ntsteps)
    oseg = atlaslabels[atlaslabels > 0].reshape(-1)
    df = pd.DataFrame(data)
    df['oseg'] = oseg
    df['oseg'] = df.oseg.astype(int)
    grand_stats = df.groupby('oseg').apply(lambda x: pd.Series(x.values.flatten().std()))
    grand_stats.columns = ['grand_std']
    grand_stats.to_csv( out_file)
    return out_file

# hack to get the hmc_transform path
def copyfile(in_file):
    from shutil import copyfile
    import os
    from pathlib import Path
    fn = Path(in_file).parts[-1]
    out_file = os.getcwd() + fn
    copyfile(in_file, out_file)
    return  out_file

def main(args=None):
    """Entry point."""
    import re
    import json
    from pathlib import Path
    from niworkflows.engine.workflows import LiterateWorkflow as Workflow
    from nipype import Function
    from nipype.pipeline import engine as pe
    from nipype.interfaces import utility as niu
    from nipype.utils.filemanip import hash_infile
    from comppsychflows.workflows.util import init_qwarp_inversion_wf
    from comppsychflows.workflows.util import init_apply_hmc_only_wf
    from comppsychflows.workflows.util import init_backtransform_wf
    from comppsychflows.workflows.util import init_scale_wf
    from comppsychflows.workflows.util import init_getstats_wf
    from nipype.interfaces.afni.preprocess import ROIStats
    from nipype.interfaces.io import DataSink

    opts = get_parser().parse_args(args=args)

    fmriprep_dir = Path(opts.fmriprep_dir)
    fmriprep_odir = fmriprep_dir / 'out'
    fmriprep_wdir = fmriprep_dir / 'wrk'
    mnitobold_dir = opts.out_path
    mnitobold_wdir = (Path(mnitobold_dir) / 'wrk')
    mnitobold_odir = (Path(mnitobold_dir) / 'out')
    dseg_path = opts.dseg_path
    mni_image = opts.mni_image
    omp_nthreads = opts.omp_nthreads
    mem_gb = opts.mem_gb
    n_dummy = opts.n_dummy

    func_wds = sorted((fmriprep_wdir/'fmriprep_wf').glob('single_subject_*_wf/func*'))
    for func_wd in func_wds:
        sub_extract = re.compile('subject_([0-9]*)')
        subject = sub_extract.findall(func_wd.as_posix())[0]
        sdc_path = func_wd / 'sdc_estimate_wf/pepolar_unwarp_wf/qwarp/Qwarp_PLUS_WARP.nii.gz'
        use_sdc =  sdc_path.exists()

        # get paths needed for workflow
        ref_path = func_wd / 'bold_reference_wf/enhance_and_skullstrip_bold_wf/n4_correct/ref_bold_corrected.nii.gz'

        hmc_transform = func_wd / 'bold_hmc_wf/fsl2itk/mat2itk.txt'
        mni_to_t1 = fmriprep_odir / f'fmriprep/sub-{subject}/anat/sub-{subject}_from-MNI152NLin2009cAsym_to-T1w_mode-image_xfm.h5'
        t1_to_bold= func_wd / 'bold_reg_wf/bbreg_wf/concat_xfm/out_inv.tfm'
        split_bolds_dir = func_wd / 'bold_split'
        split_bolds = sorted(split_bolds_dir.glob('vol*.nii.gz'))

        # We'll use the reference gen workflow to get the bids path
        validate_json = list((func_wd / 'bold_reference_wf/validate').glob('*.json'))[0]
        bold_file= json.loads(validate_json.read_text())[0][1][0]
        bold_basename = Path(bold_file).parts[-1].replace('bold.nii.gz', '')

        # If it's a rest scan replace echo 1 with echo 2
        if ('task-rest' in bold_file) and ('echo-1' in bold_file):
            bold_file = bold_file.replace('echo-1', 'echo-2')

        # define workflow
        workflow = Workflow(name=func_wd.parts[-1])

        inputnode = pe.Node(niu.IdentityInterface(
            fields=['sdc', 'ref', 'hmc_transform',
                    'mni_to_t1', 't1_to_bold',
                    'mni_image', 'dseg', 'bold_file']), name='inputnode')

        if use_sdc:
            iwf = init_qwarp_inversion_wf(omp_nthreads)
            workflow.connect([(inputnode, iwf, [('sdc', 'inputnode.warp'),
                                                ('ref', 'inputnode.in_reference')])])
            n_transforms = 3
        else:
            n_transforms = 2

        hmc_apply_wf = init_apply_hmc_only_wf(mem_gb, omp_nthreads, split_file=True)
        backtransform_wf = init_backtransform_wf(mem_gb, omp_nthreads)
        merge_transforms = pe.Node(niu.Merge(n_transforms), name='merge_xforms',
                                   run_without_submitting=True, mem_gb=mem_gb)
        # Get TSNR of minimally pocessed HMC Bold
        gettsnr = init_getstats_wf(mem_gb, omp_nthreads, n_dummy=n_dummy, name='gettsnr')

        # Scale time series by voxel mean
        scale_wf = init_scale_wf(mem_gb, omp_nthreads, n_dummy=n_dummy)

        # Calculate the voxel wise standard deviation of the scaled image
        getstd = init_getstats_wf(mem_gb, omp_nthreads, n_dummy=n_dummy, name='getstd', stat='stdev')

        # Get the TR-wise sum and count of each roi
        roi_stats = pe.Node(ROIStats(stat=['sum', 'voxels']),
                       name='roi_stats', mem_gb=mem_gb, n_procs=omp_nthreads)
        

        
        get_grand_std = pe.Node(Function(input_names=['in_file', 'dseg_file', 'out_file'],
                                     output_names=['out_file'],
                                     function=roi_grand_std),
                            name='get_grand_std')
        
        hmcxform_copy = pe.Node(Function(input_names=['in_file'],
                                 output_names=['out_file'],
                                 function=copyfile),
                        name='hmcxform_copy')
        # Use a sinker to make things pretty
        sinker = pe.Node(DataSink(), name='sinker')
        sinker.inputs.base_directory = (mnitobold_odir / func_wd.parts[-1]).as_posix()
        sinker.inputs.substitutions = [('hmcxform_copymat2itk.txt', bold_basename + 'desc-hmc_xform.txt'),
                                       ('MNItohmcbold.nii.gz', bold_basename + 'desc-MNItohmc_xform.nii.gz'),
                                       ('vol0000_xform-00000_merged_calc.nii.gz', bold_basename + 'desc-hmcscaled_bold.nii.gz'),
                                       ('vol0000_xform-00000_merged.nii.gz', bold_basename + 'desc-hmc_bold.nii.gz'),
                                       ('vol0000_xform-00000_merged_tstat.nii.gz', bold_basename + 'desc-hmc_tsnr.nii.gz'),
                                       ('vol0000_xform-00000_merged_tstat_roistat.1D', bold_basename + 'desc-hmc_roistats.1D'),
                                       ('vol0000_xform-00000_merged_calc_roistat.1D', bold_basename + 'desc-hmcscaled_roistats.1D'),
                                       ('grand_std.csv', bold_basename + 'desc-hmcscaled_grandstd.1D')
                                      ]
        
        workflow.connect([(inputnode, hmcxform_copy, [('hmc_transform', 'in_file')]),
                          (inputnode, hmc_apply_wf, [('bold_file','inputnode.name_source'),
                                                    ('bold_file', 'inputnode.bold_file'),
                                                    ('hmc_transform', 'inputnode.hmc_xforms')]),
                          (inputnode, backtransform_wf, [('mni_image', 'inputnode.template_file'),
                                                        ('dseg', 'inputnode.dseg_file'),
                                                        ('ref','inputnode.reference_image')
                                                        ]),
                          (hmc_apply_wf, backtransform_wf, [('outputnode.bold', 'inputnode.bold_file')]),
                          (inputnode, merge_transforms, [('mni_to_t1','in1'),
                                                         ('t1_to_bold', 'in2')])
                         ])
        if use_sdc:
            workflow.connect([(iwf, merge_transforms, [('outputnode.out_warp','in3')])])

        workflow.connect([(merge_transforms, backtransform_wf, [('out', 'inputnode.transforms')])])
        workflow.connect([ # Wire gettsnr
                          (hmc_apply_wf, gettsnr, [('outputnode.bold', 'inputnode.bold_file')]),
                          (backtransform_wf, gettsnr, [('outputnode.transformed_dseg', 'inputnode.dseg_file')]),
                          # Wire scale_wf
                          (hmc_apply_wf, scale_wf, [('outputnode.bold', 'inputnode.bold_file')]),
                          # Wire getstd
                          (scale_wf, getstd, [('outputnode.scaled', 'inputnode.bold_file')]),
                          (backtransform_wf, getstd, [('outputnode.transformed_dseg', 'inputnode.dseg_file')]),
                          # Wire roi_stats
                          (backtransform_wf, roi_stats, [('outputnode.transformed_dseg', 'mask_file')]),
                          (scale_wf, roi_stats, [('outputnode.scaled', 'in_file')]),
                          # Wire get_grand_std
                          (scale_wf, get_grand_std, [('outputnode.scaled','in_file')]),
                          (backtransform_wf, get_grand_std, [('outputnode.transformed_dseg','dseg_file')]),
                          # Wire sinker
                          (hmcxform_copy, sinker, [('out_file', 'mnitobold.@hmc_xforms')]),
                          (hmc_apply_wf, sinker, [('outputnode.bold', 'mnitobold.@hmc_only_bold')]),
                          (scale_wf, sinker, [('outputnode.scaled', 'mnitobold.@hmc_scaled_bold')]),
                          (backtransform_wf, sinker, [('outputnode.combined_transforms', 'mnitobold.@mni2bold_combined_xforms'),
                                                      ('outputnode.transformed_template', 'mnitobold.@transformed_template'),
                                                      ('outputnode.transformed_dseg', 'mnitobold.@transformed_dseg')]),
                          (gettsnr, sinker, [('outputnode.stat_image', 'stats.@hmc_tsnr'),
                                             ('outputnode.roi_stats', 'stats.@hmc_tsnr_roistats')]),
                          (roi_stats, sinker, [('out_file', 'stats.@scaled_roistats')]),
                          (get_grand_std, sinker, [('out_file', 'stats.@scaled_grandstd')])
                          ])
        workflow.base_dir = mnitobold_wdir.as_posix()

        # Connect inputs to workflow
        workflow.inputs.inputnode.sdc = sdc_path
        workflow.inputs.inputnode.ref = ref_path
        workflow.inputs.inputnode.hmc_transform = hmc_transform
        workflow.inputs.inputnode.mni_to_t1 = mni_to_t1
        workflow.inputs.inputnode.t1_to_bold = t1_to_bold
        workflow.inputs.inputnode.mni_image = mni_image
        workflow.inputs.inputnode.dseg = dseg_path
        workflow.inputs.inputnode.bold_file = bold_file

        wf_res = workflow.run()

if __name__ == "__main__":
    from sys import argv

    main(args=argv[1:])