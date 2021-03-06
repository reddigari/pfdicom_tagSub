# Turn off all logging for modules in this libary.
import logging
logging.disable(logging.CRITICAL)

# System imports
import      os
import      getpass
import      argparse
import      json
import      pprint
import      csv
import      re

# Project specific imports
import      pfmisc
from        pfmisc._colors      import  Colors
from        pfmisc              import  other
from        pfmisc              import  error

import      pudb
import      pftree
import      pfdicom

class pfdicom_tagSub(pfdicom.pfdicom):
    """

    A class based on the 'pfdicom' infrastructure that extracts
    and processes DICOM tags according to several requirements.

    Powerful output formatting, such as image conversion to jpg/png
    and generation of html reports is also supported.

    """

    def declare_selfvars(self):
        """
        A block to declare self variables
        """

        #
        # Object desc block
        #
        self.str_desc                   = ''
        self.__name__                   = "pfdicom_tagSub"
        self.str_version                = "2.0.8"

        # Tags
        self.b_tagList                  = False
        self.b_tagFile                  = False
        self.str_tagStruct              = ''
        self.str_tagFile                = ''
        self.d_tagStruct                = {}
        self.fileFilter                 = ''
        self.dirFilter                  = ''

        self.dp                         = None
        self.log                        = None
        self.tic_start                  = 0.0
        self.pp                         = pprint.PrettyPrinter(indent=4)
        self.verbosityLevel             = -1

    def __init__(self, *args, **kwargs):
        """
        Constructor for pfdicom_tagSub.

        Basically sets some derived class specific member variables (with
        explicit call to *this* class) and then calls super class
        constructor.
        """

        def tagStruct_process(str_tagStruct):
            self.str_tagStruct          = str_tagStruct
            if len(self.str_tagStruct):
                self.d_tagStruct        = json.loads(str_tagStruct)

        def tagFile_process(str_tagFile):
            self.str_tagFile            = str_tagFile
            if len(self.str_tagFile):
                self.b_tagFile          = True
                with open(self.str_tagFile) as f:
                    self.d_tagStruct    = json.load(f)

        def outputFile_process(str_outputFile):
            self.str_outputFileType     = str_outputFile

        # pudb.set_trace()
        pfdicom_tagSub.declare_selfvars(self)

        # Process some of the kwargs by the base class
        super().__init__(*args, **kwargs)

        for key, value in kwargs.items():
            if key == "outputFileType":     outputFile_process(value)
            if key == 'tagFile':            tagFile_process(value)
            if key == 'tagStruct':          tagStruct_process(value)
            if key == 'verbosity':          self.verbosityLevel         = int(value)
            if key == 'fileFilter':         self.fileFilter             = value
            if key == 'dirFilter':          self.dirFilter              = value

        # Set logging
        self.dp                        = pfmisc.debug(
                                            verbosity   = self.verbosityLevel,
                                            within      = self.__name__
                                            )
        self.log                       = pfmisc.Message()
        self.log.syslog(True)

    def inputReadCallback(self, *args, **kwargs):
        """
        Callback for reading files from specific directory.

        In the context of pfdicom_tagSub, this implies reading
        DICOM files and returning the dcm data set.

        """
        str_path            = ''
        l_file              = []
        b_status            = True
        l_DCMRead           = []
        filesRead           = 0

        for k, v in kwargs.items():
            if k == 'l_file':   l_file      = v
            if k == 'path':     str_path    = v

        if len(args):
            at_data         = args[0]
            str_path        = at_data[0]
            l_file          = at_data[1]

        for f in l_file:
            self.dp.qprint("reading: %s/%s" % (str_path, f), level = 5)
            d_DCMfileRead   = self.DICOMfile_read(
                                    file        = '%s/%s' % (str_path, f)
            )
            b_status        = b_status and d_DCMfileRead['status']
            l_DCMRead.append(d_DCMfileRead)
            str_path        = d_DCMfileRead['inputPath']
            filesRead       += 1

        if not len(l_file): b_status = False

        return {
            'status':           b_status,
            'l_file':           l_file,
            'str_path':         str_path,
            'l_DCMRead':        l_DCMRead,
            'filesRead':        filesRead
        }

    def inputAnalyzeCallback(self, *args, **kwargs):
        """
        Callback for doing actual work on the read data.

        This essentially means substituting tags in the
        passed list of dcm data sets.
        """
        d_DCMRead           = {}
        b_status            = False
        l_dcm               = []
        l_file              = []
        filesAnalyzed       = 0

        for k, v in kwargs.items():
            if k == 'd_DCMRead':    d_DCMRead   = v
            if k == 'path':         str_path    = v

        if len(args):
            at_data         = args[0]
            str_path        = at_data[0]
            d_DCMRead       = at_data[1]

        for d_DCMfileRead in d_DCMRead['l_DCMRead']:
            str_path    = d_DCMRead['str_path']
            l_file      = d_DCMRead['l_file']
            self.dp.qprint("analyzing: %s" % l_file[filesAnalyzed], level = 5)
            d_tagProcess        = self.tagStruct_process(d_DCMfileRead['d_DICOM'])
            for k, v in d_tagProcess['d_tagNew'].items():
                d_tagsInStruct  = self.tagsInString_process(d_DCMfileRead['d_DICOM'], v)
                str_tagValue    = d_tagsInStruct['str_result']
                setattr(d_DCMfileRead['d_DICOM']['dcm'], k, str_tagValue)
            l_dcm.append(d_DCMfileRead['d_DICOM']['dcm'])
            b_status    = True
            filesAnalyzed += 1

        return {
            'status':           b_status,
            'l_dcm':            l_dcm,
            'str_path':         str_path,
            'l_file':           l_file,
            'filesAnalyzed':    filesAnalyzed
        }

    def outputSaveCallback(self, at_data, **kwags):
        """
        Callback for saving outputs.

        In order to be thread-safe, all directory/file
        descriptors must be *absolute* and no chdir()'s
        must ever be called!
        """

        path                = at_data[0]
        d_outputInfo        = at_data[1]
        str_cwd             = os.getcwd()
        other.mkdir(self.str_outputDir)
        filesSaved          = 0
        other.mkdir(path)

        for f, ds in zip(d_outputInfo['l_file'], d_outputInfo['l_dcm']):
            ds.save_as('%s/%s' % (path, f))
            self.dp.qprint("saving: %s/%s" % (path, f), level = 5)
            filesSaved += 1

        return {
            'status':       True,
            'filesSaved':   filesSaved
        }

    def tagStruct_process(self, d_DICOM):
        """
        A method to "process" any regular expression in the passed 
        tagStruct dictionary against a current batch of DICOM files.

        This is designed to bulk replace all tags that resolve a bool
        true in the tag space with the corresponding (possibly itself
        expanded) value. For example,

            "re:.*hysician":            "%_md5|4_%tag"

        will tag any string with "hysician" in the tag with an md5 has
        (first 4 chars) of the tag:

        """

        def tagValue_process(tag, value):
            """
            For a given tag and value, process the value component for a
            special construct '#tag'. This construct in the value
            string is replaced by the tag string itself.

            If '#tag' is not in the value string, simply return the

                                    {tag: value}

            pair.
            """
            if "#tag" in value:
                value       = value.replace("#tag", tag)
            return {tag: value}

        d_tagNew    : dict  = self.d_tagStruct.copy()
        b_status    : bool  = False
        for k, v in self.d_tagStruct.items():
            if 're:' in k:
                str_reg = k.split('re:')[1]
                regex   = re.compile(r'%s' % str_reg)
                for tag in d_DICOM['d_dicomSimple']:
                    if bool(re.match(regex, tag)):
                        d_tagNew.update(tagValue_process(tag, v))
                        b_status    = True
        return {
            'status':       b_status,
            'd_tagNew':     d_tagNew
        }

    def tags_substitute(self, **kwargs):
        """
        A simple "alias" for calling the pftree method.
        """
        d_tagSub        = {}
        d_tagSub        = self.pf_tree.tree_process(
                            inputReadCallback       = self.inputReadCallback,
                            analysisCallback        = self.inputAnalyzeCallback,
                            outputWriteCallback     = self.outputSaveCallback,
                            persistAnalysisResults  = False
        )
        return d_tagSub

    def FS_filter(self, at_data, *args, **kwargs) -> dict:
        """
        Apply a filter to the string space of file and directory
        representations.

        The purpose of this method is to reduce the original space of

                        "<path>": [<"filesToProcess">]

        to only those paths and files that are relevant to the operation being
        performed. Two filters are understood, a `fileFilter` that filters
        filenames that match any of the passed search substrings from the CLI
        `--fileFilter`, and a`dirFilter` that filters directories whose
        leaf node match any of the passed `--dirFilter` substrings.

        The effect of these filters is hierarchical. First, the `fileFilter`
        is applied across the space of files for a given directory path. The
        files are subject to a logical OR operation across the comma separated
        filter argument. Thus, a `fileFilter` of "png,jpg,body" will filter
        all files that have the substrings of "png" OR "jpg" OR "body" in their
        filenames.

        Next, if a `dirFilter` has been specified, the current string path
        corresponding to the filenames being filtered is considered. Each
        string in the comma separated `dirFilter` list is exacted, and if
        the basename of the working directory contains the filter substring,
        the (filtered) files are conserved. If the basename of the working
        directory does not contain any of the `dirFilter` substrings, the
        file list is discarded.

        Thus, a `dirFilter` of "100307,100556" and a fileFilter of "png,jpg"
        will reduce the space of files to process to ONLY files that have
        a parent directory of "100307" OR "100556" AND that contain either the
        string "png" OR "jpg" in their file names.
        """

        b_status    : bool      = True
        l_file      : list      = []
        l_dirHits   : list      = []
        l_dir       : list      = []
        str_path    : str       = at_data[0]
        al_file     : list      = at_data[1]

        if len(self.fileFilter):
            al_file     = [x                                                \
                            for y in self.fileFilter.split(',')     \
                                for x in al_file if y in x]

        if len(self.dirFilter):
            l_dirHits   = [os.path.basename(str_path)                       \
                            for y in self.dirFilter.split(',')      \
                                if y in os.path.basename(str_path)]
            if len(l_dirHits):
                # Remove any duplicates in the l_dirHits:. Duplicates can
                # occur if the tokens in the filter expression map more than
                # once into the leaf node in the <str_path>, as a path that is
                #
                #                   /some/dir/in/the/space/1234567
                #
                # and a search filter on the dirspace of "123,567"
                [l_dir.append(x) for x in l_dirHits if x not in l_dir]
            else:
                # If no dir hits for this dir, then we zero out the
                # file filter
                al_file = []

        if len(al_file):
            al_file.sort()
            l_file      = al_file
            b_status    = True
        else:
            self.dp.qprint( "No valid files to analyze found in path %s!" %
                            str_path, comms = 'warn', level = 5)
            l_file      = None
            b_status    = False
        return {
            'status':   b_status,
            'l_file':   l_file
        }

    def filterFileHitList(self) -> dict:
        """
        Entry point for filtering the file filter list
        at each directory node.
        """
        d_filterFileHitList = self.pf_tree.tree_process(
                        inputReadCallback       = None,
                        analysisCallback        = self.FS_filter,
                        outputWriteCallback     = None,
                        applyResultsTo          = 'inputTree',
                        applyKey                = 'l_file',
                        persistAnalysisResults  = True
        )
        return d_filterFileHitList


    def run(self, *args, **kwargs):
        """
        The run method calls the base class run() to
        perform initial probe and analysis.

        Then, it effectively calls the method to perform
        the DICOM tag substitution.

        """
        b_status        = True
        d_tagSub        = {}
        b_timerStart    = False
        d_filter        = {}

        self.dp.qprint(
                "Starting pfdicom_tagSub run... (please be patient while running)",
                level = 1
                )

        for k, v in kwargs.items():
            if k == 'timerStart':   b_timerStart    = bool(v)

        if b_timerStart:
            other.tic()

        # Run the base class, which probes the file tree
        # and does an initial analysis. Also suppress the
        # base class from printing JSON results since those
        # will be printed by this class
        d_pfdicom       = super().run(
                                        JSONprint   = False,
                                        timerStart  = False
                                    )


        if d_pfdicom['status']:
            if len(self.fileFilter) or len(self.dirFilter):
                d_filter    = self.filterFileHitList()
                b_status    = d_filter['status']

            str_startDir    = os.getcwd()
            os.chdir(self.str_inputDir)
            if b_status:
                d_tagSub    = self.tags_substitute()
                b_status    = b_status and d_tagSub['status']
            os.chdir(str_startDir)

        d_ret = {
            'status':       b_status,
            'd_pfdicom':    d_pfdicom,
            'd_tagSub':     d_tagSub,
            'd_filter':     d_filter,
            'runTime':      other.toc()
        }

        if self.b_json:
            self.ret_dump(d_ret, **kwargs)

        self.dp.qprint('Returning from pfdicom_tagSub run...', level = 1)

        return d_ret
