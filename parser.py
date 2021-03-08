#!/usr/bin/python3

import ast, io, sys, tokenize

IGNORE_TOKENS = set([tokenize.COMMENT, tokenize.DEDENT, tokenize.ENCODING, tokenize.ENDMARKER, tokenize.INDENT, tokenize.NEWLINE, tokenize.NL])

ASSIGNMENT = None


def parse_file(pathname):
	"""
		return tests specified in file as a list of dicts containing the parameters for each test 
	"""
	try:
		with open(pathname, 'r') as f:
			return parse_stream(f, pathname)
	except TestSpecificationError as e:
		print(e, file=sys.stderr)
		sys.exit(1)	

		
def parse_stream(stream, source_name):
	"""
		return tests specified in stream as a list of dicts containing the parameters for each test 
	"""
	tests = []
	global_variables = {}
	for (line_number, values) in parse_values(stream, source_name):
		if not values:
			continue
		parameters = parse_line_assignments(values, f"{source_name}:{line_number}: ")
		if 'label' not in parameters:
			global_variables.update(parameters)
		else:
			test = global_variables.copy()
			test['source_name'] = str(source_name)
			test['line_number'] = str(line_number)
			test.update(parameters)
			tests.append(test)			
	return tests

		
def parse_line_assignments(values, error_prefix):
	"""
		return a dict containing the parameters specified by values
		a singleton value is converted to a value for the parameter 'label'
	"""
	assignments = {}
	last_word = None
	while values:
		value = values.pop(0)
		if value == ASSIGNMENT:

			if (not last_word or
				not last_word.isidentifier() or
				not(values) or
				values[0] == ASSIGNMENT):
				raise TestSpecificationError(f"{error_prefix}syntax error in assignment")

			if last_word in assignments:
				raise TestSpecificationError(f"{error_prefix}error - multiple assignments to variable '{last_word}'")

			if len(values) == 1 or values[2:3] == [ASSIGNMENT]:
				assignment_rhs = values.pop(0)
			else:
				assignment_rhs = []
				while values and values[1:2] != [ASSIGNMENT]:
					assignment_rhs.append(values.pop(0))

			assignments[last_word] = assignment_rhs
			last_word = None
		elif isinstance(value, str): 
			if last_word:
				if 'label' in assignments:
					raise TestSpecificationError(f"{error_prefix}error - multiple labels")
				assignments['label'] = last_word
			last_word = value
		else:
			raise TestSpecificationError(f"{error_prefix}error - invalid test specification")
	if last_word:
		if 'label' in assignments:
			raise TestSpecificationError(f"{error_prefix}error - multiple labels")
		assignments['label'] = last_word
	return assignments
																
		
def parse_values(stream, source_name):
	"""
		return a list of (line_number, value_list) tuples
		where value_list is the values parsed from that line

		value_list can contain strings, lists, dicts and the special value ASSIGNMENT
		list or dicts in value_list will only not contain any other type than strings, lists or dicts 
		
		shell-like bare-words and merge of adjacent tokens is implemented
		
		triple-quoted strings can span multiple lines
		Note: no text on the remainder of a line following a list or dict 		
	"""
	combined_lines = ''
	combined_lines_number = 1
	parse = []
	for (line_number, line) in enumerate(stream, 1):
		if combined_lines == '':
			combined_lines_number = line_number
		combined_lines += line
		last_token = None
		values = []

		try:
			for token in tokenize.generate_tokens(io.StringIO(combined_lines).readline):

				if token.type == tokenize.ERRORTOKEN:
					raise TestSpecificationError(f"{source_name}:{line_number}:{token.start[1]}: syntax error")
				
				if token.type != tokenize.STRING and '=' in token.string and  len(token.string) > 1:
					raise TestSpecificationError(f"{source_name}:{line_number}:{token.start[1]}: syntax error in assignment")
				
				if not token.string or token.type in IGNORE_TOKENS:
					continue
					
				if token.string in '[{' and values and values[-1] == ASSIGNMENT and not last_token:
					#print('line: ', repr(combined_lines[token.start[1]:]))
					value = stringize(eval(combined_lines[token.start[1]:]))
					print(value)
					#print('value: ', value)
					values.append(value)
					break
		
				if not last_token or (last_token.end != token.start or token.string == '='):
					if last_token:
						values.append(get_token_characters(last_token))
					if token.string == '=':
						values.append(ASSIGNMENT)
						last_token = None
					else:
						last_token = token
				else:
					last_token = FakeToken(last_token, token) # shell-like merging of adjacent strings
					
			if last_token:
				values.append(get_token_characters(last_token))
				
		except (tokenize.TokenError,SyntaxError):
			# a multi-line string or expression has produced an exception
			# continue adding more lines until string/expression is complete 
			continue

		combined_lines = ''
		parse.append((combined_lines_number, values))

	if combined_lines:
		raise TestSpecificationError(f"{source_name}:{combined_lines_number} unclosed expression")
	return parse


def stringize(x):
	"""convert to str all sub-objects in x which are not dicts and lists"""
	if isinstance(x, dict):
		for (k,v) in x.items():
			x[k] = stringize(v)
	elif isinstance(x, list):
		for i in range(len(x)):
			x[i] = stringize(x[i])
	elif not isinstance(x, str):
		x = str(x)
	return x


def get_token_characters(token):
	"""return characters of token"""
	if token.type == tokenize.STRING:
		return ast.literal_eval(token.string)
	else:
		return token.string

		
class FakeToken:
	"""return a tokenize.TokenInfo look-like formed from 2 adjacent tokens"""
	def __init__(self, token1, token2):
		self.type = tokenize.STRING
		self.start = token1.start
		self.end = token2.end
		self.string = repr(get_token_characters(token1) + get_token_characters(token2))


class TestSpecificationError(Exception):
	pass

TEST_STRING = """

# aaaa	

max_cpu_seconds=45

program=hello.py
files=hello.py

test1 max_cpu_seconds=10 expected_stdout=kkk command=hello.py "arg 1" 'arg 2' *.c

test2 stdin=5

v1='''1
2
3
'''

v2='''a
b
c
'''

v3 = [4,5,6]

v4 = [7,
8,
9]

v5 = {'a':'b'}

v6 = {
'c'  : 'd'
}

label=last

test42 expected_stdout='''line 1
line 2
line 3
''' expected_stderr='''e1
e2
e3
'''
""" 

if __name__ == "__main__":
	import pprint
	if sys.argv[1:]:
		for pathname in sys.argv[1:]:
			pprint.pprint(parse_file(pathname))
	else:
		stream = io.StringIO(TEST_STRING)
		pprint.pprint(parse_stream(stream, "<test-string>"))