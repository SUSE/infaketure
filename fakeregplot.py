#
# GNU Plot exporter for Fakereg
#
__author__ = 'BOFH <bo@suse.de>'

import os
import ConfigParser


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
    pcp_data = "/home/bo/gnuplot/advanced"
    for fname, script in GNUPlotExporter("fakeregplot.conf", pcp_data).generate().items():
        fname = os.path.join(pcp_data, fname)
        print "Writing {script} ...\t".format(script=fname),
        scr_fh = open(fname, "w")
        scr_fh.write(script)
        scr_fh.close()
        os.chmod(fname, 0744)
        print "done"
