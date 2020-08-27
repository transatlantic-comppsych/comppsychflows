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

class TStatInputSpec(AFNICommandInputSpec):

    in_file = File(
        desc="input file to 3dTstat",
        argstr="%s",
        position=-1,
        mandatory=True,
        exists=True,
        copyfile=False,
    )
    index = Str(desc="AFNI indexing string for in_file")
    out_file = File(
        name_template="%s_tstat",
        desc="output image file name",
        argstr="-prefix %s",
        name_source="in_file",
    )
    mask = File(desc="mask file", argstr="-mask %s", exists=True)
    options = Str(desc="selected statistical output", argstr="%s")


class TStat(AFNICommand):
    """Compute voxel-wise statistics using AFNI 3dTstat command
    For complete details, see the `3dTstat Documentation.
    <https://afni.nimh.nih.gov/pub/dist/doc/program_help/3dTstat.html>`_
    Examples
    --------
    >>> from nipype.interfaces import afni
    >>> tstat = afni.TStat()
    >>> tstat.inputs.in_file = 'functional.nii'
    >>> tstat.inputs.args = '-mean'
    >>> tstat.inputs.out_file = 'stats'
    >>> tstat.cmdline
    '3dTstat -mean -prefix stats functional.nii'
    >>> res = tstat.run()  # doctest: +SKIP
    """

    _cmd = "3dTstat"
    input_spec = TStatInputSpec
    output_spec = AFNICommandOutputSpec

    def _format_arg(self, name, trait_spec, value):
        if name == "in_file":
            arg = trait_spec.argstr % value
            if isdefined(self.inputs.index):
                arg += self.inputs.index
            return arg
        return super(TStat, self)._format_arg(name, trait_spec, value)

    def _parse_inputs(self, skip=None):
        """Skip the arguments without argstr metadata
        """
        return super(TStat, self)._parse_inputs(skip=("index"))