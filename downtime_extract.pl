#!/usr/bin/perl

##############
# Dumps downtimes created by thruk into json
# Created by Andrew W.
##############

use strict;
use warnings;

use Data::Dumper;
use JSON::XS;
use File::Slurp;
use Getopt::Long qw(:config no_ignore_case bundling pass_through);
use Log::Log4perl qw(:levels);
use vars qw(%opt);

# get a new logger
my $logger = Log::Log4perl->get_logger();

# define logging layout to use
my $layout = Log::Log4perl::Layout::PatternLayout->new("%d{yyyy-MM-dd HH:mm:ss} - [%p] (%P) --> %m%n");

# create a new appender
my $appender = Log::Log4perl::Appender->new(
	"Log::Log4perl::Appender::Screen",
	stderr => 0,
);

# add layout to appender and appender to logger
$appender->layout($layout);
$logger->add_appender($appender);

# set log level to info for now
$logger->level($INFO);

# set defaults
$opt{dir}	= undef;
$opt{output}	= undef;
$opt{verbose}	= undef;

# get options
GetOptions (\%opt,
	"dir|d=s",
	"output|o=s",
	"single|s=s",
	"simulation|S",
	"verbose|v",
	"help|h",
) or $logger->logdie("Could not process command line arguments");

# increase log level to debug based on verbosity
$logger->level($DEBUG) if ($opt{verbose});

# show command line args
$logger->debug("Command line arguments\n" . Dumper(\%opt));

# print help if necessary
usage() if ($opt{help} || !$opt{dir} || !$opt{output});

# remove trailing slash on dir
$opt{dir} = $1 if($opt{dir} =~ /(.*)\/$/);

# read in all files
my @files;
if ($opt{single}) {
	$logger->info("Going to process $opt{dir}/$opt{single}");
	@files = "$opt{dir}/$opt{single}" if(-f "$opt{dir}/$opt{single}");
} else {
	$logger->info("Going to process $opt{dir}/*.tsk");
	@files = glob("$opt{dir}/*.tsk");
}

# nothing to process
if (!@files) {
	# let user know there is nothing to do
	$logger->info("No files to process writing empty json array to $opt{output}");

	# if not in simulation write empty json to file
	# because if no files are to be processed that
	# means there are no downtimes
	write_file($opt{output}, "[]\n") if (!$opt{simulation});

	# exit without error
	$logger->info("All done");
	exit(0);
}

# loop through all files
my @data;
for my $dfile (@files) {
	# skip if this is not a regular file
	next unless (-f $dfile);

	# let user know what is being processed
	$logger->info("Processing $dfile");

	# read contents of the file
	my $content .= read_file($dfile);

	# log file contents
	$logger->debug("Contents of $dfile\n$content");

	# eval content to something perl can use
	my $temp;
	eval('$temp= '. $content . ';');

	# show data eval of contents
	$logger->debug("Data of $dfile\n" . Dumper($temp));

	# add to output
	push(@data, $temp);
}

# show data eval of contents
$logger->debug("Final data\n" . Dumper(@data));

# create json encoder
my $encoder = JSON::XS->new
		->ascii
		->pretty
		->allow_blessed
		->allow_nonref;

# encode to json
my $output = $encoder->encode(\@data);

# show full json output
$logger->debug("Final output\n$output");

# write output to file if not in simulation
write_file($opt{output}, $output) if (!$opt{simulation});

# log output
$logger->info("Wrote output to $opt{output}");
$logger->info("All done");

# shows help
sub usage {
print <<"EOF";
Usage: $0 --dir|d --output|o --single|s --simulation|S --verbose|v --help|h

	--dir|d		Directory where Thruk downtimes are stored
	--output|o	File where we will store JSON output
	--single|s	Process only a single dowtime file which you specify
	--simulation|S	Only shows output does not write file
	--verbose|v	Turn on verbose output
	--help|h	Displays help
EOF
exit(1);
}
