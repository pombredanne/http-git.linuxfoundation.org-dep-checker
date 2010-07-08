# Create your views here.
from django.template import Context, loader
from django.shortcuts import render_to_response, get_object_or_404
from compliance.linkage.models import Test, File, Lib, License, Aliases, LibLicense, \
                                      FileLicense, Policy, TestForm, LicenseForm, PolicyForm, \
                                      LibLicenseForm, FileLicenseForm, AliasesForm, \
                                      StaticSymbol, StaticLibSearchPath, SearchPathForm
from django.http import HttpResponse, HttpResponseRedirect
from django.http import Http404
from django.conf import settings
from django.db.models import Q

from compliance import load_static, task

import sys
import os
import re
import urllib

# used for binding and policy
is_static = '(static)'

### each of these views has a corresponding html page in ../templates/linkage

# task status page - intended for calling in javascript
def taskstatus(request):
    tm = task.TaskManager()
    return HttpResponse(tm.read_status())

# main page
def index(request):
    from site_settings import gui_name, gui_version
    return render_to_response('linkage/index.html', {'name': gui_name, 'version': gui_version})

# test run detail page
def detail(request, test_id):
    t, masterlist = render_detail(test_id)
    return render_to_response('linkage/detail.html', {'test': t, 'master': masterlist, 'tab_results': True})
  
# results list page - this is also a form, for test deletions
def results(request):
    if request.method == 'POST': # If the form has been submitted...
        testlist = request.POST.get('testlist', '')
        if testlist != '':
            tests = testlist.split(",")

            # delete all the selected tests from the database
            for test in tests:
                if test != '':
                    q = Test.objects.filter(id = test)
                    q.delete()
                    q = File.objects.filter(test = test)
                    q.delete()
                    q = Lib.objects.filter(test = test)
                    q.delete()

    latest_test_list = Test.objects.all().order_by('-test_date')
    return render_to_response('linkage/results.html', {'latest_test_list': latest_test_list, 'tab_results': True})

# licenses entry/maintenance page
def licenses(request):
    if request.method == 'POST': # If the form has been submitted...
        mode = urllib.unquote(request.POST.get('submit'))
        print mode

        if re.search("^Add License", mode):   
            licenseform = LicenseForm(request.POST) # A form bound to the POST data
            # request to add data
            if licenseform.is_valid(): # All validation rules pass
                licenseform.save()
            else:
                print licenseform.errors

        if re.search("^Add", mode) and re.search("Aliases", mode):
            aliasesform = AliasesForm(request.POST) # A form bound to the POST data
            # request to add data - we may have multiple aliases to add
            if aliasesform.is_valid(): # All validation rules pass
                license = aliasesform.cleaned_data['license']
                for i in range(1,10):
                    ainput = request.POST.get('alinput' + str(i), '')
                    if ainput:
                        aliasdata = Aliases(license = license, alias = ainput)
                        aliasdata.save()
                        print ainput

        if re.search("^Delete Selected Licenses", mode): 
            # delete request
            licenselist = request.POST.get('licenselist', '')
            if licenselist != '':
                delete_records(License, licenselist)

        if re.search("^Delete Selected Aliases", mode): 
            # delete request
            aliaslist = request.POST.get('aliaslist', '')
            if aliaslist != '':
                # not by id here, so don't call delete_records
                records = aliaslist.split(",")

                for record in records:
                    if record != '':
                        q = Aliases.objects.filter(license = record)
                        q.delete()

    licenseform = LicenseForm() # An unbound form
    aliasesform = AliasesForm() # An unbound form

    latest_license_list = License.objects.all().order_by('longname')
    # we represent this one differently in the gui, pre-arrange things here
    aliases_list = Aliases.objects.values('license').distinct()
    
    for l in aliases_list:
        alias_list = Aliases.objects.values('alias').filter(license = l['license'])
        aliases = ''
        for a in alias_list:
            aliases += a['alias'] + ' | '
        # chomp the last "or" off
        l['alias'] = aliases[:-3]

    # we want multiple input boxes to enter a number of aliases per license, at once
    al_input = []
    for i in range(1,10):
        al_input.append('<input type="text" size="6" name="alinput' + str(i) + '">')

    return render_to_response('linkage/licenses.html', {
                              'latest_license_list': latest_license_list,
                              'latest_aliases_list': aliases_list, 
                              'licenseform': licenseform,
                              'aliasesform': aliasesform,
                              'input_list': al_input,
                              'tab_licenses': True })

# policy list page - this is also a form, for policy deletions/updates
def policy(request):
    from site_settings import show_rank

    if request.method == 'POST': # If the form has been submitted...
        mode = urllib.unquote(request.POST.get('submit'))

        if re.search("^Add", mode):
            policyform = PolicyForm(request.POST) # A form bound to the POST data
            # request to add data
            if policyform.is_valid(): # All validation rules pass
                policyform.save()
       
        else:
            # delete request       
            policylist = request.POST.get('policylist', '')
            if policylist != '':
                delete_records(Policy, policylist)

    policyform = PolicyForm() # An unbound form

    latest_policy_list = Policy.objects.all().order_by('-edit_date')

    return render_to_response('linkage/policy.html', {
                              'show_rank': show_rank,
                              'latest_policy_list': latest_policy_list, 
                              'policyform': policyform, 
                              'tab_policy': True })

# target/library/license binding page
def lbindings(request):

    if request.method == 'POST': # If the form has been submitted...
        mode = urllib.unquote(request.POST.get('submit'))

        if re.search("^Add Target", mode):
            targetlicenseform = FileLicenseForm(request.POST) # A form bound to the POST data
            # request to add data
            if targetlicenseform.is_valid(): # All validation rules pass
                targetlicenseform.save()

        if re.search("^Add Library", mode):
            liblicenseform = LibLicenseForm(request.POST) # A form bound to the POST data
            # request to add data
            if liblicenseform.is_valid(): # All validation rules pass
                liblicenseform.save()       

        if re.search("^Update Target", mode):
            update_file_bindings()

        if re.search("^Update Library", mode):
            update_lib_bindings()

        if re.search("^Delete Selected", mode) and re.search("Target Bindings", mode):
            # delete request       
            targetlicenselist = request.POST.get('targetlicenselist', '')
            if targetlicenselist != '':
                delete_records(FileLicense, targetlicenselist)

        if re.search("^Delete Selected", mode) and re.search("Library Bindings", mode):
            # delete request       
            liblicenselist = request.POST.get('liblicenselist', '')
            if liblicenselist != '':
                delete_records(LibLicense, liblicenselist)

    targetlicenseform = FileLicenseForm() # An unbound form
    liblicenseform = LibLicenseForm() # An unbound form

    latest_targetlicense_list = FileLicense.objects.all().order_by('file')
    latest_liblicense_list = LibLicense.objects.all().order_by('library')

    return render_to_response('linkage/lbindings.html', {
                              'latest_targetlicense_list': latest_targetlicense_list, 
                              'latest_liblicense_list': latest_liblicense_list, 
                              'targetlicenseform': targetlicenseform, 
                              'liblicenseform': liblicenseform, 
                              'tab_lbindings': True })

# settings - miscellaneous things to set, used for static db reloading
def settings_form(request):

    # This is the task to be executed.
    def static_reload_task():
        lib_list = load_static.get_library_list()
        sys.stdout.write("COUNT: %d\n" % len(lib_list))
        sys.stdout.flush()
        StaticSymbol.objects.all().delete()
        for lib in lib_list:
            sys.stdout.write("ITEM: " + lib + "\n")
            sys.stdout.flush()
            load_static.load_symbols(lib)

    infomsg = None
    tm = task.TaskManager()

    if request.method == 'POST':
        if 'reload_static' in request.POST:
            if not tm.is_running():
                tm.start(static_reload_task)
                infomsg = "Reloading static database.  This may take a while."
            else:
                infomsg = "The static database is already being reloaded."
        elif 'change_search_paths' in request.POST:
            search_path_form = SearchPathForm(request.POST)
            if search_path_form.is_valid():
                path_list = search_path_form.cleaned_data['dirlist'].split("\n")
                path_list = [x.strip() for x in path_list]
                StaticLibSearchPath.objects.all().delete()
                for path_str in path_list:
                    path = StaticLibSearchPath(path=path_str)
                    path.save()
            else:
                infomsg = "One of the directory paths could not be found."
        else:
            infomsg = "Could not understand the form request."

    # Load the current search paths, and create the form.
    search_paths = [x.path for x in StaticLibSearchPath.objects.all()]
    search_path_str = "\n".join(search_paths)
    search_path_form = SearchPathForm({ 'dirlist': search_path_str })

    return render_to_response('linkage/settings.html', 
                              { 'info_message': infomsg, 
                                'tab_settings': True,
                                'reload_running': tm.is_running(),
                                'search_path_form': search_path_form })

# process test form - this is where the real work happens
def test(request):
    cli_command = settings.CLI_COMMAND + " -c"
    if request.method == 'POST': # If the form has been submitted...
        testform = TestForm(request.POST) # A form bound to the POST data
        if testform.is_valid(): # All validation rules pass
            target = testform.cleaned_data['target']
            disable_static = testform.cleaned_data['disable_static']
            if disable_static:
                cli_command += " --no-static "
            do_search = testform.cleaned_data['do_search']
            if do_search:
                target_dir = testform.cleaned_data['target_dir']
                cli_command += "-s " + target_dir
            cli_command += " " + target
            recursion = testform.cleaned_data['recursion']
            cli_command += " " + str(recursion)
            # form doesn't have the id, but we can get the db model and then get it
            testdata = testform.save(commit=False)       
            testdata.save()
            testid = testdata.id

            errmsg = do_dep_check(cli_command, testid)
     
            # if we got an error, delete the test entry
            if errmsg:
                q = Test.objects.filter(id = testid)
                q.delete()
                t = []
                masterlist = []            
            
            else:
                # render the results
                t, masterlist = render_detail(testid)

            return render_to_response('linkage/detail.html', 
                {'test': t, 'master': masterlist, 'error_message': errmsg })
            
    else:
        testform = TestForm() # An unbound form

    return render_to_response('linkage/test.html', {
        'testform': testform,
        'tab_test': True,
    })

### these are all basically documentation support

# doc page
def documentation(request):
    from site_settings import gui_name, gui_version

    # Read the standalone docs, and reformat for the gui
    docs = ''
    status = 0

    try:
        f = open(settings.STATIC_DOC_ROOT + "/docs/index.html", 'r')

    except:
        # docs are created yet, try to do it
        status = os.system("cd " + settings.STATIC_DOC_ROOT + "/docs && make")
        if status != 0:
            status = os.system("cd " + settings.STATIC_DOC_ROOT + "/docs && ./text-docs-to-html > index.html.addons")
            if status == 0:
                status = os.system("cd " + settings.STATIC_DOC_ROOT + "/docs && cat index.html.base index.html.addons index.html.footer > index.html")
            else:
                docs = "<b>Error, no index.html in compliance/media/docs.</b><br>"
                docs += "If working with a git checkout or tarball, please type 'make' in the top level directory.<br>"
                docs += "</body>"

    # something worked above
    if not docs:
        f = open(settings.STATIC_DOC_ROOT + "/docs/index.html", 'r')
        doc_index = []
        for line in f:
            #replace the div styles for embedded use
            line = line.replace('<div id="lside">', '<div id="lside_e">')
            line = line.replace('<div id="main">', '<div id="main_e">')
            line = line.replace('<img src="', '<img src="/site_media/docs/')
            doc_index.append(line)
        f.close()
    
        # drop the first 11 lines
        docs = ''.join(doc_index[11:])

    return render_to_response('linkage/documentation.html', 
                              {'name': gui_name, 
                               'version': gui_version, 
                               'gui_docs': docs })

# this does not have a corresponding dirlist.html
# this is dynamic filetree content fed to jqueryFileTree for the test.html file/dir selection
# script for jqueryFileTree points to /linkage/dirlist/
def dirlist(request):
    # filter out some directories that aren't useful from "/"
    not_wanted = [ '/proc', '/dev', '/sys', '/initrd' ]
    r=['<ul class="jqueryFileTree" style="display: none;">']
    try:
        d=urllib.unquote(request.POST.get('dir'))
        content = os.listdir(d)
        # slows things a little, but looks more like 'ls'
        for f in sorted(content, key=unicode.lower):
            ff=os.path.join(d,f)
            if ff not in not_wanted and f != 'lost+found':
                if os.path.isdir(ff): 
                    r.append('<li class="directory collapsed"><a href="#" rel="%s/">%s</a></li>' % (ff,f))
                else:
                    e=os.path.splitext(f)[1][1:] # get .ext and remove dot
                    r.append('<li class="file ext_%s"><a href="#" rel="%s">%s</a></li>' % (e,ff,f))
        r.append('</ul>')
    except Exception,e:
        r.append('Could not load directory: %s' % str(e))
    r.append('</ul>')
    return HttpResponse(''.join(r))

### utility functions

# run the back end with given parameters and push the data into the database
def do_dep_check(cli_command, testid):
    # capture the output and push to the database
    lastdepth = 1
    lastfile = ''
    errmsg = ''
    dbdata = ''           
    for dbdata in os.popen(cli_command).readlines():
        # check for no result - these are known exit messages from the cli
        if not re.search("(does not|was not found|not an ELF)", dbdata):
            dbdata = dbdata.rstrip("\r\n")
            # format for level 1 is: depth, parent, dep
            # format for level 1 + N is: depth, child path, child, dep, dep...
            deps = dbdata.split(",")

            # write the file record
            depth = int(deps[0])
            testfile = deps[1]
            # the top level file may show multiple times, only get the first one
            if depth == 1 and testfile != lastfile:
                filedata = File(test_id = testid, file = testfile, level = depth, parent_id = 0)
                filedata.save()
                fileid = filedata.id
                lastfile = testfile
                parentid = fileid
                filedata.parent_id = parentid
                filedata.save()
            elif depth != 1:
                # FIXME - right now we're not really doing anything with these
                filedata = File(test_id = testid, file = testfile, level = depth, parent_id = 0)
                filedata.save()
                fileid = filedata.id
                # the 'child' files get the parent's id
                filedata.parent_id = parentid
                filedata.save()
                  
            # now the lib records
            offset = 2
            # child records have the lib path and the parent dep
            if depth > 1:
                offset = 3
            for lib in deps[offset:len(deps)]:
                static = False
                if re.search(is_static, lib):
                    lib = lib.split()[0]
                    static = True
                # we link file_id to parent_id of the file for recursion
                libdata = Lib(test_id = testid, file_id = parentid, library = lib, static = static, level = depth, parent_id = 0)
                libdata.save()
                libid = libdata.id
                       
                # the 'child' libs get the parent's id
                if depth == 1:
                    parentlibid = libid
                libdata.parent_id = parentlibid
                libdata.save()
                        
        else:
            # do feedback in the gui from here
            errmsg += dbdata

    # cli didn't return anything
    if not dbdata:
        errmsg = "no result..."

    if not errmsg:
        # update the license bindings
        update_license_bindings()

    return errmsg

# delete table records requested by id from one of the input forms
def delete_records(table, rlist):
            
    records = rlist.split(",")

    for record in records:
        if record != '':
            q = table.objects.filter(id = record)
            q.delete()

# update both file and library bindings
def update_license_bindings():
    update_lib_bindings()
    update_file_bindings()

# update Lib records for license bindings
def update_lib_bindings():
    llist = LibLicense.objects.all().order_by('library')
    # bind both the dynamic and static version
    for ll in llist:
        Lib.objects.filter(library = ll.library).update(license = ll.license)

# update File records for license bindings
def update_file_bindings():
    flist = FileLicense.objects.all().order_by('file')
    for fl in flist:
        File.objects.filter(file = fl.file).update(license = fl.license)

# list of aliases for a license
def get_license_aliases(license):
    alias_list = Aliases.objects.values('alias').filter(license = license)
    alist = []
    for a in alias_list:
        alist.append(a['alias'])
    return alist

# check a target/library pair for policy violations
def check_policy(flicense, llicense, library, static, issue):
    # is the lib dynamic or static?
    ltype = 'Dynamic'
    if static:
        ltype = 'Static'

    # it's possible that the license assigned to the target or library is one of
    # the aliases, in which case we need the 'official' name for the policy check
    pllicense = llicense # we want to display both names in the report, if present
    pflicense = flicense

    llicenseset = Aliases.objects.filter(alias = llicense)
    if llicenseset:
        # can only be one match
        pllicense = llicenseset[0].license
    if  llicense != pllicense:
        # plug in the alias (real name)
        llicense = llicense + ' (' + pllicense + ')'

    flicenseset = Aliases.objects.filter(alias = flicense)
    if flicenseset:
        # can only be one match
        pflicense = flicenseset[0].license
    if flicense != pflicense:
        flicense = flicense + ' (' + pflicense + ')'
      
    policyset = Policy.objects.filter(tlicense = pflicense, dlicense = pllicense)
    policyset = policyset.filter(Q(relationship = ltype) | Q(relationship = 'Both'))
    # if we got multiple matches, just return - bad policies
    if policyset and policyset.count() < 2:
        status = policyset[0].status
        # only set the issue flag for the target coloring for the disallowed case
        if status == 'D':
            issue = issue or True
        llicense = flag_policy_issue(llicense, status)

    # highlight if there is no policy defined      
    if not policyset and flicense != 'TBD':
        llicense = flag_policy_issue(llicense, 'U')

    # modify the target when there's been a problem somewhere in the whole license set
    if issue:
        flicense = flag_policy_issue(flicense, 'D')

    return issue, llicense, flicense
        
# flag a policy issue for the test results rendering
def flag_policy_issue(value, status):
    # to highlight the issues
    tag_start = '<span class="'
    tag_mid = '">'
    tag_end = '</span>'
    tcolor = "yellow"
    if status == 'A':
        tcolor = "green"
    if status == 'D':
        tcolor = "red"
        tag_end += '<img src="/site_media/images/red_flag.png" width="16" height="16" alt="red_flag.png">'
    value = tag_start + tcolor + tag_mid + value + tag_end
    return value

# pre-render the table data for the detail page
def render_detail(test_id):
    t = get_object_or_404(Test, pk=test_id)
    # update any new bindings
    update_license_bindings()
    # all we want is the level 1 files
    fileset = t.file_set.filter(level = 1)
    libset = t.lib_set.all()

    # the table renders too slow walking through the one-to-many of
    # files -> libs, prefill a list with file, license, libs, lib_license 
    # and indent the recursion level here, template just blobs out the table

    flist = []
    llist = []
    for file in fileset:
        flist.append(file.file)
        if file.license:
            llist.append(file.license)
        else:
            llist.append("TBD")

    lastid = ''
    masterlist = []
    liblist = ''
    # this gets incremented before the first record is complete
    counter = -1
    spacer = "&nbsp;&nbsp;"
    
    policy_issue = False
    for lib in libset:
        fileid = lib.file_id
        # no indent for level 1
        level = lib.level - 1
        # we don't use this at the moment
        parent = lib.parent_id
        if lib.license:
            policy_issue, llicense, flicense = check_policy(llist[counter], lib.license, lib.library, lib.static, policy_issue)
        else:
            llicense = 'TBD'
        if fileid != lastid:
            if liblist != '':
                if policy_issue:
                    llist[counter] = flicense
                masterlist.append({'file': flist[counter], 'license': llist[counter], 'libs': liblist, 'statics': staticlist, 'licenses': liclist})
            liblist = lib.library
            counter += 1
            # reset and check against the new binary, if we have a license
            if lastid:            
                policy_issue = False
            if lib.license:
                policy_issue, llicense, flicense = check_policy(llist[counter], lib.license, lib.library, lib.static, policy_issue)
            staticlist = ''
            if lib.static:
                staticlist = 'x'           
            liclist = llicense
        else:
            liblist += '<BR>' + spacer * level + lib.library
            staticlist += '<BR>'
            if lib.static:
                staticlist += 'x'
            liclist += '<BR>' + llicense
        lastid = fileid

    # add the last record
    if policy_issue:
        llist[counter] = flicense

    masterlist.append({'file': flist[counter], 'license': llist[counter], 'libs': liblist, 'statics': staticlist, 'licenses': liclist})
    
    return t, masterlist

