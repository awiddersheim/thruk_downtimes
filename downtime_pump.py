#!/usr/bin/python

import logging
import datetime
import argparse
import json
import pprint
import requests
from os import environ
from time import sleep

# add command line arguments
parser = argparse.ArgumentParser(
	prog="downtime_pump",
	description="""
		Pumps recurring downtimes into Monitoring
		using the Thruk interface.
	"""
)

parser.add_argument(
	"-d",
	"--downtime-file",
	action="store",
	dest="input_file",
	default="downtimes.json",
	help="Location of JSON formatted downtime file. (default: %(default)s)"
)

auth_group = parser.add_argument_group(
	"Authentication",
	(
		"Password can be specified either on the command line or "
		"the environment variable 'THRUK_PASSWORD'. "
		"The password specified on the command line takes precedence."
	)
)

auth_group.add_argument(
	"-u",
	"--user",
	action="store",
	dest="username",
	default=None,
	help="User to authenticate with."
)

auth_group.add_argument(
	"-p",
	"--password",
	action="store",
	dest="password",
	default=None,
	help="Password to authenticate with."
)

parser.add_argument(
	"-U",
	"--url",
	action="store",
	dest="url",
	default="https://127.0.0.1/thruk/cgi-bin/cmd.cgi",
	help="URL to Thruk's cmd.cgi page (default: %(default)s)"
)

parser.add_argument(
	"-a",
	"--author",
	action="store",
	dest="author",
	default="Nagios",
	help="Author to use when adding downtimes. (default: %(default)s)"
)

parser.add_argument(
	"-t",
	"--timeout",
	action="store",
	dest="timeout",
	default=10,
	type=int,
	help="Timeout in second(s) when connecting to Thruk. (default: %(default)s)"
)

parser.add_argument(
	"-z",
	"--sleep",
	action="store",
	dest="sleep",
	default=1,
	type=int,
	help="How long to sleep in between retries when communicating with Thruk. (default: %(default)s)"
)

parser.add_argument(
	"-r",
	"--retries",
	action="store",
	dest="retries",
	default=10,
	type=int,
	help="Number of times to retry sending downtime data to Thruk. (default: %(default)s)"
)

parser.add_argument(
	"-s",
	"--simulation",
	action="store_true",
	default=False,
	dest="simulation",
	help="Turn on simulation which only shows what would be done without actually doing it."
)

parser.add_argument(
	"-v",
	"--verbose",
	action="count",
	default=0,
	dest="verbose",
	help="Increase verbosity. Can be specified up to 4 times. (default: %(default)s)"
)

# parse arguments
options = parser.parse_args()

# get a logger
logger = logging.getLogger("logger")
loggerRequests = logging.getLogger("requests")

# set logging level based on verbosity
logger.setLevel(logging.INFO)
loggerRequests.setLevel(logging.WARNING)
if options.verbose > 0:
	logger.setLevel(logging.DEBUG)
if options.verbose > 1:
	loggerRequests.setLevel(logging.INFO)
if options.verbose > 2:
	loggerRequests.setLevel(logging.DEBUG)

# logging formatter
formatter = logging.Formatter(
	"%(asctime)s.%(msecs).03d - [%(levelname)s] (%(process)s) (%(processName)s)(%(threadName)s) --> %(message)s",
	"%Y-%m-%d %H:%M:%S"
)

# handler for logging to the console
streamHandler = logging.StreamHandler()
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)

# starting up
logger.info("Starting up")

# check to see if a password was
# specified on the comamnd line
if options.password:
	logger.debug("Using password from command line")
else:
	# check to see if a password was
	# supplied using an environment variable
	logger.debug("Checking for password in environment variable")
	options.password = environ.get("THRUK_PASSWORD")

# hide password from debug output
password = options.password
if options.password is not None:
	options.password = "xxxxxx"

# show command line options
logger.debug(
	"Command line options:\n%s",
	pprint.pformat(vars(options))
)

# assign password
options.password = password

# show help if a password
# was supplied but no user
if options.password and not options.username:
	logger.error("Password was specified without a username")
	parser.print_help()
	exit(1)

try:
	# read in file contents
	logger.debug("Opening %s", options.input_file)
	with open(options.input_file, "r") as content_file:
		content = json.loads(content_file.read())
except IOError as e:
	logger.error(
		"Error working with [%s: %s]",
		options.input_file,
		e
	)
	exit(1)

# if no downtimes than exit
if not len(content):
	logger.info("No downtimes to process")
	exit(0)

# log the data retrieved
logger.debug(
	"Raw data from file:\n%s",
	pprint.pformat(content)
)

# get a date object
date_object = datetime.datetime.now()

# print time if in verbose
logger.debug(
	"Date: %s Day: %s Weekday: %s",
	date_object,
	date_object.day,
	date_object.isoweekday()
)

# list to store downtimes
downtimes = list()

# loop through each downtime
for item in content:
	# dictionary to store downtime payload
	payload = dict()

	# loop through each schedule
	for schedule in item["schedule"]:
		# figure out if anything needs to be
		# put into downtime
		if schedule["type"] == "day" \
		or schedule["type"] == "week" \
		and str(date_object.isoweekday()) in str(schedule["week_day"]) \
		or schedule["type"] == "month" \
		and date_object.day == schedule["day"]:
			# log info about downtime
			logger.info(
				"Processing downtime tgt: %s, hst: %s, svc: %s, hg: %s, sg: %s, be: %s, fxd: %s, dur: %d, flxrng: %d, typ: %s, wd: %s, d: %d, hr: %d, min: %d",
				item["target"],
				item["host"],
				item["service"] or None,
				item["hostgroup"],
				item["servicegroup"],
				item["backends"],
				item["fixed"],
				item["duration"],
				item["flex_range"],
				schedule["type"],
				schedule["week_day"],
				schedule["day"],
				schedule["hour"],
				schedule["minute"]
			)

			# get new time objects with hour minutes and seconds replaced
			date_object = date_object.replace(hour = schedule["hour"])
			date_object = date_object.replace(minute = schedule["minute"])
			date_object = date_object.replace(second = 0)

			# create payload that will get passed as parameters
			payload["cmd_mod"]	= 2
			payload["fixed"]	= 1
			payload["com_data"]	= item["comment"]
			payload["com_author"]	= options.author
			payload["start_time"]	= int(date_object.strftime("%s"))
			payload["end_time"]	= payload["start_time"] + item["duration"] * 60
			payload["childoptions"] = item["childoptions"]
			payload["backend"]	= item["backends"]

			# determine type
			if item["target"] == "host":
				payload["cmd_typ"] = 55
				key = "host"
			elif item["target"] == "service":
				payload["cmd_typ"] = 56
				payload["service"] = item["service"]
				key = "host"
			elif item["target"] == "hostgroup":
				payload["cmd_typ"] = 84
				key = "hostgroup"
			elif item["target"] == "servicegroup":
				payload["cmd_typ"] = 122
				key = "servicegroup"
			else:
				logger.error(
					"Could not process downtime with target (%s)",
					item["target"]
				)
				continue

			# loop through each target
			for target in item[key]:
				# add to payload
				payload[key] = target

				# add payload to downtime list
				downtimes.append(payload.copy())

# loop through each downtime
for downtime in downtimes:
	# show the url that is going
	# to get used when connecting
	logger.info(
		"Calling (%s)",
		requests.Request(
			"POST",
			options.url,
			params=downtime
		).prepare().url
	)

	# skip to next iteration of loop
	# and do not try to actually connect
	if options.simulation:
		continue

	# set up retry loop
	for retry in range(options.retries + 1):
		# logg if this is a retry
		if retry > 0:
			logger.info(
				"Retry (%d) out of (%d) while trying to process downtime",
				retry,
				options.retries
			)

		try:
			# issue request to url
			r = requests.post(
				options.url,
				params=downtime,
				verify=False,
				auth=(options.username, options.password),
				timeout=options.timeout
			)

			# log any errors
			if r.status_code != 200:
				logger.error(
					"Could not process downtime which returned with a status code of (%d)",
					r.status_code
				)
			else:
				logger.info(
					"Finished processing downtime with status code (%d)",
					r.status_code
				)

				# break from loop
				break
		except (
			requests.exceptions.ConnectionError,
			requests.exceptions.HTTPError,
			requests.exceptions.TooManyRedirects
		) as message:
			# these are fatal errors
			logger.error("Permanent error processing downtime: %s", message)
			exit(1)
		except requests.exceptions.Timeout:
			logger.error("Could not process downtime due to timeout (%d)", options.timeout)
		except Exception as message:
			logger.error("Could not process downtime due to an unknown error: %s", message)

		# handle retry logic
		if options.retries > 0 and retry < options.retries:
			logger.info("Sleeping for (%d) second(s) before retrying", options.sleep)

			# sleep between retries
			sleep(options.sleep)
		else:
			logger.error(
				"Could not process downtime because the retry limit was reached after (%d) retries",
				options.retries
			)
			exit(1)

# let user know dump completed
if options.simulation:
	logger.info("All done running in simulation mode where no action was taken")
else:
	logger.info("All done")
