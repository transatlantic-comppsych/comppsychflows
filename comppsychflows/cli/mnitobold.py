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


def main(args=None):
    """Entry point."""
    import re
    import json
    from pathlib import Path
    from niworkflows.engine.workflows import LiterateWorkflow as Workflow
    from nipype.pipeline import engine as pe
    from nipype.interfaces import utility as niu
    from nipype.utils.filemanip import hash_infile
    from ..workflows.util import init_qwarp_inversion_wf
    from ..workflows.util import init_apply_hmc_only_wf
    from ..workflows.util import init_backtransform_wf

    opts = get_parser().parse_args(args=args)

    fmriprep_dir = Path(opts.fmriprep_dir)
    fmriprep_odir = fmriprep_dir / 'out'
    fmriprep_wdir = fmriprep_dir / 'wrk/wrk'
    mnitobold_dir = opts.out_path
    dseg_path = opts.dseg_path
    mni_image = opts.mni_image
    omp_nthreads = opts.omp_nthreads
    mem_gb = opts.mem_gb

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

        workflow.connect([(inputnode, hmc_apply_wf, [('bold_file','inputnode.name_source'),
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
        workflow.base_dir = mnitobold_dir

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