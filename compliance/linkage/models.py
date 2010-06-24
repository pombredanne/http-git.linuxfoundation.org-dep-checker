from django.db import models
from django.forms import ModelForm, forms
from django import forms
import os

# Create your models here.

# setup some defaults/choices
rchoices = tuple(enumerate(range(0, 100)))
RECURSION_CHOICES = rchoices[1:]
DEFAULT_USER = os.environ['USER']
REL_CHOICES = (('Static','Static'), ('Dynamic','Dynamic'), ('Both', 'Both'))
RANK_CHOICES = (('Low','Low'), ('Normal','Normal'), ('Critical', 'Critical'))

def license_choices():
    # get the available licenses to populated the form drop-downs
    licenses = License.objects.all().order_by('license')
    # need a tuple for the drop-down
    choices = []
    # no default
    choices.append(('',''))
    for lic in licenses:
        selector = lic.license + " " + lic.version
        choices.append((selector, selector))

    return choices

def library_choices():
    # get the available libraries to populated the form drop-downs
    libraries = Lib.objects.values('library').distinct()
    # need a tuple for the drop-down
    choices = []
    # no default
    choices.append(('',''))
    for lib in libraries:
        choices.append((lib['library'], lib['library']))

    return choices

def file_choices():
    # get the available targets to populated the form drop-downs
    files = File.objects.filter(level = 1).values('file').distinct()
    # need a tuple for the drop-down
    choices = []
    # no default
    choices.append(('',''))
    for f in files:
        choices.append((f['file'], f['file']))

    return choices

class Test(models.Model):
    do_search = models.BooleanField('Search for target file in target directory')
    recursion = models.IntegerField('Recursion level for analysis', 
                                    default = '1', choices = RECURSION_CHOICES)
    target = models.CharField('File/Path to test', max_length=200)
    target_dir = models.CharField('Target Directory', max_length=200, blank=True)
    test_date = models.DateTimeField('test date', auto_now=True)
    user = models.CharField(max_length=200, blank=True, default = DEFAULT_USER)
    project = models.CharField(max_length=200, blank=True)
    comments = models.CharField(max_length=200, blank=True)
    def __unicode__(self):
        return self.target

class File(models.Model):
    test = models.ForeignKey(Test)
    file = models.CharField(max_length=200)
    license = models.CharField(max_length=200, blank=True)
    level = models.IntegerField()
    parent_id = models.IntegerField()
    def __unicode__(self):
        return self.file

class Lib(models.Model):
    test = models.ForeignKey(Test)
    file = models.ForeignKey(File)
    library = models.CharField(max_length=200)
    license = models.CharField(max_length=200, blank=True)
    level = models.IntegerField()
    parent_id = models.IntegerField()
    def __unicode__(self):
        return self.library

class License(models.Model):
    license = models.CharField('License', max_length=200)
    version = models.CharField('Version', max_length=20)
    def __unicode__(self):
        return self.license

class LibLicense(models.Model):
    library = models.CharField('Library', max_length=200, unique=True)
    license = models.CharField('License', max_length=200)

class FileLicense(models.Model):
    file = models.CharField('Library', max_length=200, unique=True)
    license = models.CharField('License', max_length=200)

class Policy(models.Model):
    tlicense = models.CharField('Target License', max_length=200)
    dlicense = models.CharField('Dependency License', max_length=200)
    relationship = models.CharField('Relationship', max_length=20,
                                    default = 'Static', choices = REL_CHOICES)
    rank = models.CharField('Rank', max_length=20,
                            default = 'Low', choices = RANK_CHOICES)
    edit_date = models.DateTimeField('test date', auto_now=True)
    def __unicode__(self):
        return self.tlicense

class Dep(models.Model):
    file = models.ForeignKey(File)
    lib = models.ForeignKey(Lib)
    #def __unicode__(self):
    #    return self.lib

class TestForm(ModelForm):   
    class Meta:
        model = Test

class FileForm(ModelForm):
    class Meta:
        model = File

class LibForm(ModelForm):
    class Meta:
        model = Lib

class LicenseForm(ModelForm):
    class Meta:
        model = License

class PolicyForm(ModelForm):
    class Meta:
        model = Policy

    tlicense = forms.ChoiceField()
    dlicense = forms.ChoiceField()

    def __init__(self, *args, **kwargs):
        super(PolicyForm, self).__init__(*args, **kwargs)
        self.fields['tlicense'].choices = license_choices()
        self.fields['dlicense'].choices = license_choices()

class LibLicenseForm(ModelForm):
    class Meta:
        model = LibLicense

    license = forms.ChoiceField()
    library = forms.ChoiceField()
 
    def __init__(self, *args, **kwargs):
        super(LibLicenseForm, self).__init__(*args, **kwargs)
        self.fields['license'].choices = license_choices()
        self.fields['library'].choices = library_choices()

class FileLicenseForm(ModelForm):
    class Meta:
        model = FileLicense

    license = forms.ChoiceField()
    file = forms.ChoiceField()
 
    def __init__(self, *args, **kwargs):
        super(FileLicenseForm, self).__init__(*args, **kwargs)
        self.fields['license'].choices = license_choices()
        self.fields['file'].choices = file_choices()

