from nipype.pipeline import engine as pe
from nipype.interfaces import utility as niu
from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from niworkflows.interfaces import CopyHeader
from nipype.interfaces import afni
from sdcflows.workflows.pepolar import _fix_hdr
from templateflow.api import get as get_template


def init_qwarp_inversion_wf(omp_nthreads=1,
                           name="qwarp_invert_wf"):
    """
    Invert a warp produced by 3dqwarp and convert it to an ANTS formatted warp
    Workflow Graph
        .. workflow ::
            :graph2use: orig
            :simple_form: yes
            from sdcflows.workflows.base import init_qwarp_inversion_wf
            wf = init_qwarp_inversion_wf()
    Parameters
    ----------
    name : str
        Name for this workflow
    omp_nthreads : int
        Parallelize internal tasks across the number of CPUs given by this option.
    Inputs
    ------
    warp : pathlike
        The warp you want to invert.
    in_reference : pathlike
        The baseline reference image (must correspond to ``epi_pe_dir``).
    Outputs
    -------
    out_warp : pathlike
        The corresponding inverted :abbr:`DFM (displacements field map)` compatible with
        ANTs.
    """
    from ..interfaces.afni import InvertWarp
    workflow = Workflow(name=name)
    workflow.__desc__ = """\
A warp produced by 3dQwarp was inverted by `3dNwarpCat` @afni (AFNI {afni_ver}).
""".format(afni_ver=''.join(['%02d' % v for v in afni.Info().version() or []]))

    inputnode = pe.Node(niu.IdentityInterface(
        fields=['warp', 'in_reference']), name='inputnode')

    outputnode = pe.Node(niu.IdentityInterface(
        fields=['out_warp']),
        name='outputnode')

    invert = pe.Node(InvertWarp(), name='invert', n_procs=omp_nthreads)
    invert.inputs.outputtype = 'NIFTI_GZ'
    to_ants = pe.Node(niu.Function(function=_fix_hdr), name='to_ants',
                      mem_gb=0.01)

    cphdr_warp = pe.Node(CopyHeader(), name='cphdr_warp', mem_gb=0.01)

    workflow.connect([
        (inputnode, invert, [('warp', 'in_file')]),
        (invert, cphdr_warp, [('out_file', 'in_file')]),
        (inputnode, cphdr_warp, [('in_reference', 'hdr_file')]),
        (cphdr_warp, to_ants, [('out_file', 'in_file')]),
        (to_ants, outputnode, [('out', 'out_warp')]),
    ])

    return workflow


def init_apply_hmc_only_wf(mem_gb, omp_nthreads,
                               name='apply_hmc_only',
                               use_compression=True,
                               split_file=False,
                               interpolation='LanczosWindowedSinc'):
    """
    Resample in native (original) space.
    This workflow resamples the input fMRI in its native (original)
    space in a "single shot" from the original BOLD series.
    Parameters
    ----------
    mem_gb : :obj:`float`
        Size of BOLD file in GB
    omp_nthreads : :obj:`int`
        Maximum number of threads an individual process may use
    name : :obj:`str`
        Name of workflow (default: ``bold_std_trans_wf``)
    split_file : :obj:`bool`
        Whether the input file should be splitted (it is a 4D file)
        or it is a list of 3D files (default ``False``, do not split)
    interpolation : :obj:`str`
        Interpolation type to be used by ANTs' ``applyTransforms``
        (default ``'LanczosWindowedSinc'``)
    Inputs
    ------
    bold_file
        Individual 3D volumes, not motion corrected
    name_source
        BOLD series NIfTI file
        Used to recover original information lost during processing
    hmc_xforms
        List of affine transforms aligning each volume to ``ref_image`` in ITK format
    Outputs
    -------
    bold
        BOLD series, resampled in native space, including all preprocessing
    """
    from niworkflows.engine.workflows import LiterateWorkflow as Workflow
    from niworkflows.func.util import init_bold_reference_wf
    from niworkflows.interfaces.itk import MultiApplyTransforms
    from niworkflows.interfaces.nilearn import Merge
    from nipype.interfaces.fsl import Split as FSLSplit

    workflow = Workflow(name=name)
    workflow.__desc__ = """\
The BOLD time-series (including slice-timing correction when applied)
were resampled onto their original, native space by applying
{transforms}.
These resampled BOLD time-series will be referred to as *preprocessed
BOLD in original space*, or just *preprocessed BOLD*.
""".format(transforms="""\
the transforms to correct for head-motion""")

    inputnode = pe.Node(niu.IdentityInterface(fields=[
        'name_source', 'bold_file', 'hmc_xforms']),
        name='inputnode'
    )

    outputnode = pe.Node(
        niu.IdentityInterface(fields=['bold']),
        name='outputnode')

    bold_transform = pe.Node(
        MultiApplyTransforms(interpolation=interpolation, float=True, copy_dtype=True),
        name='bold_transform', mem_gb=mem_gb * 3 * omp_nthreads, n_procs=omp_nthreads)

    merge = pe.Node(Merge(compress=use_compression), name='merge',
                    mem_gb=mem_gb * 3)

    workflow.connect([
        (inputnode, merge, [('name_source', 'header_source')]),
        (bold_transform, merge, [('out_files', 'in_files')]),
        (merge, outputnode, [('out_file', 'bold')]),
    ])

    # Input file is not splitted
    if split_file:
        bold_split = pe.Node(FSLSplit(dimension='t'), name='bold_split',
                             mem_gb=mem_gb * 3)
        workflow.connect([
            (inputnode, bold_split, [('bold_file', 'in_file')]),
            (bold_split, bold_transform, [
                ('out_files', 'input_image'),
                (('out_files', _first), 'reference_image'),
            ])
        ])
    else:
        workflow.connect([
            (inputnode, bold_transform, [('bold_file', 'input_image'),
                                         (('bold_file', _first), 'reference_image')]),
        ])

    def _aslist(val):
        return [val]
    workflow.connect([
        (inputnode, bold_transform, [(('hmc_xforms', _aslist), 'transforms')]),
    ])
    return workflow


def _first(inlist):
    return inlist[0]


def init_backtransform_wf(mem_gb, omp_nthreads,
                               name='backtransform',
                               interpolation='LanczosWindowedSinc'):
    """
    Transform standard space images back to bold_hmc space
    and extract roi level stats for each tr.
    Parameters
    ----------
    mem_gb : :obj:`float`
        Size of BOLD file in GB
    omp_nthreads : :obj:`int`
        Maximum number of threads an individual process may use
    name : :obj:`str`
        Name of workflow (default: ``bold_std_trans_wf``)
    interpolation : :obj:`str`
        Interpolation type to be used by ANTs' ``applyTransforms``
        (default ``'LanczosWindowedSinc'``)
    Inputs
    ------
    template_file
        template file to be transformed to bold space
    reference_image
        reference image for template space
    dseg_file
        deterministic parcelated file in template space to be transformed to bold space
    bold_file
        bold image to extract stats from
    transforms
        list of transformations for registration from template space to bold space
    Outputs
    -------
    combined_transforms
        combined template to bold transformation
    transformed_template
        template transformed to bold space
    transformed_dseg
        dset transformed to bold space
    roi_stats
        stats on each roi from each tr

    """
    from niworkflows.engine.workflows import LiterateWorkflow as Workflow
    from niworkflows.interfaces.fixes import FixHeaderApplyTransforms as ApplyTransforms
    from nipype.interfaces.afni.preprocess import ROIStats
    
    workflow = Workflow(name=name)

    inputnode = pe.Node(niu.IdentityInterface(fields=[
        'template_file', 'reference_image','dseg_file', 'bold_file', 'transforms']),
        name='inputnode'
    )

    outputnode = pe.Node(
        niu.IdentityInterface(fields=['combined_transforms',
                                      'transformed_template',
                                      'transformed_dseg',
                                      'roi_stats']),
        name='outputnode')

    combine_transforms = pe.Node(
        ApplyTransforms(interpolation=interpolation,
            float=True,
            print_out_composite_warp_file=True,
            output_image = 'MNItohmcbold.nii.gz'),
        name='combine_transforms', mem_gb=mem_gb, n_procs=omp_nthreads)

    resample_template = pe.Node(
        ApplyTransforms(interpolation=interpolation, float=True,),
        name='resample_template', mem_gb=mem_gb, n_procs=omp_nthreads)

    resample_parc = pe.Node(ApplyTransforms(
        dimension=3,
        interpolation='MultiLabel'),
        name='resample_parc', mem_gb=mem_gb, n_procs=omp_nthreads)
    
    roi_stats = pe.Node(ROIStats(stat=['mean', 'sigma', 'median', 'sum', 'voxels']),
                       name='roi_stats', mem_gb=mem_gb, n_procs=omp_nthreads)
    
    workflow.connect([
        (inputnode, combine_transforms, [('transforms', 'transforms')]),
        (inputnode, combine_transforms, [('reference_image', 'reference_image')]),
        (inputnode, combine_transforms, [('template_file', 'input_image')]),
        (inputnode, resample_template, [('template_file', 'input_image')]),
        (inputnode, resample_template, [('reference_image', 'reference_image')]),
        (inputnode, resample_parc, [('reference_image', 'reference_image')]),
        (inputnode, resample_parc, [('dseg_file', 'input_image')]),
        (inputnode, roi_stats, [('bold_file', 'in_file')]),
        (combine_transforms, resample_template, [('output_image', 'transforms')]),
        (combine_transforms, resample_parc, [('output_image', 'transforms')]),
        (resample_parc, roi_stats, [('output_image', 'mask_file')]),
        (combine_transforms, outputnode, [('output_image', 'combined_transforms')]),
        (resample_template, outputnode, [('output_image', 'transformed_template')]),
        (resample_parc, outputnode, [('output_image', 'transformed_dseg')]),
        (roi_stats, outputnode, [('out_file', 'roi_stats')]),
    ])
    
    return workflow

def init_scale_wf(mem_gb, omp_nthreads, n_dummy=None, scale_stat='mean',
                               name='scale'):
    """
    Run afni's voxel level mean scaling
    Parameters
    ----------
    mem_gb : :obj:`float`
        Size of BOLD file in GB
    omp_nthreads : :obj:`int`
        Maximum number of threads an individual process may use
    n_dummy: :obj: `int`
        Number of dummy scans at the begining of the bold to discard when calculating the mean
    scale_stat : :obj:`str`
        Name of the flag for the statistic to scale relative to (defaul: ``mean``) 
    name : :obj:`str`
        Name of workflow (default: ``bold_std_trans_wf``)
    Inputs
    ------
    bold_file
        bold image to scale, should probably be head motion corrected first
    Outputs
    -------
    scaled
        scaled bold time series
    """
    from niworkflows.engine.workflows import LiterateWorkflow as Workflow
    from niworkflows.interfaces.fixes import FixHeaderApplyTransforms as ApplyTransforms
    from nipype.interfaces.afni import Calc
    from ..interfaces.afni import TStat 
    
    workflow = Workflow(name=name)

    inputnode = pe.Node(niu.IdentityInterface(fields=[
        'bold_file']),
        name='inputnode'
    )

    outputnode = pe.Node(
        niu.IdentityInterface(fields=['scaled']),
        name='outputnode')

    scale_ref = pe.Node(
        TStat(args=f'-{scale_stat}', index=f'[{n_dummy}..$]', outputtype='NIFTI_GZ'),
        name='scale_ref', mem_gb=mem_gb, n_procs=omp_nthreads)

    scale = pe.Node(
        Calc(outputtype='NIFTI_GZ', expr='min(200, a/b*100)*step(a)*step(b)'),
        name='scale', mem_gb=mem_gb, n_procs=omp_nthreads)
    
    workflow.connect([
        (inputnode, scale_ref, [('bold_file', 'in_file')]),
        (inputnode, scale, [('bold_file', 'in_file_a')]),
        (scale_ref, scale, [('out_file', 'in_file_b')]),
        (scale, outputnode, [('out_file', 'scaled')])
    ])
    
    return workflow

def init_getstats_wf(mem_gb, omp_nthreads, n_dummy=0, stat='cvarinvNOD',name='getstats'):
    """
    Run some 3dtstat (tsnr by default) and save out roi level stats
    Parameters
    ----------
    mem_gb : :obj:`float`
        Size of BOLD file in GB
    omp_nthreads : :obj:`int`
        Maximum number of threads an individual process may use
    n_dummy: :obj: `int`
        Number of dummy scans at the begining of the bold to discard when calculating the mean
    scale_stat : :obj:`str`
        Name of the flag for the statistic to extract (defaul: ``tsnr``) 
    name : :obj:`str`
        Name of workflow (default: ``tsnrstats_wf``)
    Inputs
    ------
    bold_file
        bold image to get tsnr from, should probably be head motion corrected first
    dseg_file
        deterministic parcelated file in template space to be transformed to bold space
    Outputs
    -------
    stat_image
        scaled bold time series
    roi_stats
        stats on each roi from each tr
    """ 
    from niworkflows.engine.workflows import LiterateWorkflow as Workflow
    from niworkflows.interfaces.fixes import FixHeaderApplyTransforms as ApplyTransforms
    from ..interfaces.afni import TStat
    from nipype.interfaces.afni.preprocess import ROIStats

    workflow = Workflow(name=name)

    inputnode = pe.Node(niu.IdentityInterface(fields=[
        'bold_file', 'dseg_file']),
        name='inputnode'
    )

    outputnode = pe.Node(
        niu.IdentityInterface(fields=['stat_image',
                                      'roi_stats',
                                      ]),
        name='outputnode')

    getstat = pe.Node(
        TStat(options=f'-{stat}', index=f'[{n_dummy}..$]', outputtype='NIFTI_GZ'),
        name='getstat', mem_gb=mem_gb, n_procs=omp_nthreads)

    roi_stats = pe.Node(ROIStats(stat=['sum', 'voxels']),
                   name='roi_stats', mem_gb=mem_gb, n_procs=omp_nthreads)

    workflow.connect([
        (inputnode, getstat, [('bold_file', 'in_file')]),
        (inputnode, roi_stats, [('dseg_file', 'mask_file')]),
        (getstat, roi_stats, [('out_file', 'in_file')]),
        (getstat, outputnode, [('out_file', 'stat_image')]),
        (roi_stats, outputnode, [('out_file', 'roi_stats')])
    ])
    return workflow