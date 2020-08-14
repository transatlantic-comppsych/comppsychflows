"""AFNI tool interfaces"""

from nipype.interfaces.afni.base import (
    AFNICommandBase,
    AFNICommand,
    AFNICommandInputSpec,
    AFNICommandOutputSpec,
    AFNIPythonCommandInputSpec,
    AFNIPythonCommand,
    Info,
    no_afni,
)

from nipype.interfaces.base import (
    CommandLineInputSpec,
    CommandLine,
    TraitedSpec,
    traits,
    isdefined,
    File,
    InputMultiPath,
    Undefined,
    Str,
    InputMultiObject,
)
class InvertWarpInputSpec(AFNICommandInputSpec):
    in_file = File(
        desc="warp to be inverted",
        position=-1,
        mandatory=True,
        exists=True,
        copyfile=False,
        argstr="'INV(%s)'"
    )
    out_file = File(
        name_template="%s_inverted",
        desc="output to the file",
        argstr="-prefix %s",
        name_source="in_file",
        position=1,
    )
    
class InvertWarp(AFNICommand):
    """A wrapper around 3dNwarpCat that just inverts the transformation
    For complete details, see the `3dNwarpCat Documentation.
    <https://afni.nimh.nih.gov/pub/dist/doc/program_help/3dNwarpCat.html>`_
    Examples
    --------
    >>> from nipype.interfaces import afni
    >>> iw = afni.InvertWarp()
    >>> iw.inputs.in_file = 'functional.nii'
    >>> iw.cmdline  # doctest: +ELLIPSIS
    '3dNwarpCat -prefix functional_inverted functional.nii'
    >>> res = iw.run()  # doctest: +SKIP
    """

    _cmd = "3dNwarpCat"
    input_spec = InvertWarpInputSpec
    output_spec = AFNICommandOutputSpec