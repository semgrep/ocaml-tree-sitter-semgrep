%{
%}

%token <unit> EOF
%token <unit> VARIABLE
%token <unit> NUMBER
%token <unit> COMMENT
%token <unit> X1 "*"
%token <unit> X2 "+"
%token <unit> X3 "-"
%token <unit> X4 "/"
%token <unit> X5 ";"
%token <unit> X6 "="
%token <unit> X7 "^"

%left X2 X3
%left X1 X4
%right X7

%start <unit> program
%%

program: list(intermediate1) EOF { } 

intermediate1: 
 | assignment_statement { } 
 | expression_statement { } 


assignment_statement: VARIABLE "=" expression ";"  { } 

expression_statement: expression ";"  { } 

expression: 
 | VARIABLE { } 
 | NUMBER { } 
 | expression "+" expression  { } 
 | expression "-" expression  { } 
 | expression "*" expression  { } 
 | expression "/" expression  { } 
 | expression "^" expression  { } 
