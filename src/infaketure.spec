#
# spec file for package faketure
#
# Copyright (c) 2015 SUSE LINUX Products GmbH, Nuernberg, Germany.
#
# All modifications and additions to the file contributed by third parties
# remain the property of their copyright owners, unless otherwise agreed
# upon. The license for this file, and modifications and additions to the
# file, is the same license as for the pristine package itself (unless the
# license for the pristine package is not an Open Source License, in which
# case the license is the MIT License). An "Open Source License" is a
# license that conforms to the Open Source Definition (Version 1.9)
# published by the Open Source Initiative.

# Please submit bugfixes or comments via http://bugs.opensuse.org/
#


%{?!python:%define python python}
%{?!pybasever:%{expand:%%define pybasever %(%{__python} -c "import sys ; print sys.version[:3]")}}
%if 0%{?fedora} < 13 && 0%{?rhel} <= 6
%{!?py_sitedir: %define py_sitedir %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%endif

Name:           infaketure
Version:        0.2
Release:        1
Summary:        Tool to generate a load for installed SUSE Manager instance

Group:          Productivity/Databases/Tools
License:        MIT
Url:            https://gitlab.suse.de/bofh/fakereg-ks
Source0:        %{name}-%{version}.tar.bz2
BuildRoot:      %{_tmppath}/%{name}-%{version}-build

BuildRequires:  %{python}-devel
%if 0%{?suse_version}
Requires:       python = %{pybasever}
%endif
Requires:       sudo

%description
SUMA Fake infrastructure is a software to create a number of a registered clients, that does not actually exist and generate a load from them.


%prep
%setup

%build
CFLAGS="$RPM_OPT_FLAGS" %{__python} setup.py build

%install
%{__python} setup.py install --no-bin --skip-build --root="$RPM_BUILD_ROOT" --prefix=%{_prefix} --record=INSTALLED_FILES
mkdir -p $RPM_BUILD_ROOT/%{_bindir}
#mkdir -p $RPM_BUILD_ROOT%{_mandir}/man1
install -m0755 infaketure.py $RPM_BUILD_ROOT/%{_bindir}/infaketure
install -m0755 infaketure-plot.py $RPM_BUILD_ROOT/%{_bindir}/infaketure-plot

#install -m0644 doc/fakereg.1 $RPM_BUILD_ROOT%{_mandir}/man1/

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
%defattr(-,root,root,-)
%dir %{python_sitelib}/infaketure
%dir %{_sysconfdir}/infaketure
%config %{_sysconfdir}/infaketure/scenario.scn
%config %{_sysconfdir}/infaketure/plot.conf
%doc LICENSE
#%{_mandir}/man1/*.1*
%{_bindir}/*

%changelog
