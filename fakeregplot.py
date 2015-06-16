#!/usr/bin/python
#
# GNU Plot exporter for Fakereg
#
__author__ = 'BOFH <bo@suse.de>'

import os
import sys
import ConfigParser
from optparse import OptionParser


class GNUPlotExporter(object):
    """
    Generate a number of scripts across the PCP metrics.
    """

    DATA_EXT = ".data"
    INFO_EXT = ".info"

    def __init__(self, config_path, metrics_path):
        """
        Constructor.

        :param metrics_path:
        :return:
        """
        self._path = metrics_path
        self._config = ConfigParser.RawConfigParser()
        self._config.read(config_path)

    def _parse_options(self, raw):
        """
        Parse comma-separated key=value structures into a dictionary.
        In order to place a comma inside the value, value itself should be
        surrounded with double quote (") symbol.

        :param raw:
        :return:
        """
        key = list()
        value = list()
        parsed = {}
        f_prs = False
        f_str = True
        for elm in raw:
            if elm == '"' and not f_prs:
                f_prs = True
                continue
            elif elm == '"' and f_prs:
                f_prs = False
                continue

            if f_prs:
                value.append(elm)
                continue

            if elm == ',':
                parsed[''.join(key).strip()] = ''.join(value).strip()
                key = list()
                value = list()
                f_str = True
                continue
            elif elm == '=' and f_str:
                f_str = False
            elif f_str:
                key.append(elm)
            else:
                value.append(elm)
        parsed[''.join(key).strip()] = ''.join(value).strip()

        return parsed

    def generate(self):
        """
        Generate GNU Plot scripts.

        :return:
        """
        scripts = dict()
        for section in self._config.sections():
            body = ['#!/usr/bin/gnuplot -p', 'set grid']
            structure = {"meta": {"title": section, "filename": section.lower() + ".sh"}, "data": list()}
            for directive in self._config.options(section):
                directive = directive.strip()
                if directive.startswith("meta "):
                    structure["meta"][directive.split(" ")[-1]] = self._config.get(section, directive)
                elif directive.startswith("probe "):
                    plot = {"plot": directive.split(" ")[-1] + ".data"}
                    for key, value in self._parse_options(self._config.get(section, directive)).items():
                        if key == "column":
                            plot["u"] = value
                        elif key == "title":
                            plot["t"] = value
                    structure["data"].append(plot)
                else:
                    raise Exception("Unknown config directive: " + directive.split(" ")[0])

            body.append('set title "{0}"'.format(structure["meta"]["title"]))
            plot = []
            for data in structure["data"]:
                segment = list()
                segment.append('"{0}"'.format(data.pop("plot")))
                segment.append("u {0}".format(data.pop("u")))
                if "t" in data:
                    segment.append('t "{0}"'.format(data.pop("t")))
                segment.append("w lines")  # Default
                plot.append(" ".join(segment))
            body.append("plot {0}".format(", \\\n     ".join(plot)))

            scripts[structure["meta"]["filename"]] = '\n'.join(body)

        return scripts

if __name__ == '__main__':
    args = OptionParser(version="Bloody Alpha, 0.1", prog='fakeregplot',
                        description='Generate GNU Plot views from the Fakereg PCP data.')
    args.add_option("-p", "--path", help="Path to the PCP snapshot", action="store")
    args.add_option("-c", "--config", help="Path to the configuration", action="store")
    if not [elm for elm in sys.argv if elm.startswith("--path")]:
        sys.argv.append("--help")
    options, args = args.parse_args()

    options.config = options.config or "./fakeregplot.conf"
    if not os.path.exists(options.config):
        print 'Error: cannot access "{conf}" configuration'.format(conf=options.config)
        sys.exit(1)

    if not os.path.exists(options.path):
        print 'Error: snapshot "{snapshot}" does not exists'.format(snapshot=options.path)
        sys.exit(1)
    elif not [elm for elm in os.listdir(options.path) if elm.split(".")[-1] in ["data", "info"]]:
        print 'Error: snapshot "{snapshot}" does not seems to be a valid'.format(snapshot=options.path)
        sys.exit(1)

    for fname, script in GNUPlotExporter(options.config, options.path).generate().items():
        fname = os.path.join(options.path, fname)
        print "Writing {script} ...\t".format(script=fname),
        scr_fh = open(fname, "w")
        scr_fh.write(script)
        scr_fh.close()
        os.chmod(fname, 0744)
        print "done"

