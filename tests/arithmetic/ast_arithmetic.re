/* Auto-generated by codegen_type */
type comment =string
and number =string
and variable =string
and intermediate1 =
 | Intermediate_type1(assignment_statement)
 | Intermediate_type2(expression_statement)
and expression =
 | Intermediate_type3(variable)
 | Intermediate_type4(number)
 | Intermediate_type5((expression, +, expression))
 | Intermediate_type6((expression, -, expression))
 | Intermediate_type7((expression, *, expression))
 | Intermediate_type8((expression, /, expression))
 | Intermediate_type9((expression, ^, expression))
and assignment_statement =(variable, =, expression, ;)
and expression_statement =(expression, ;)
and program =list(intermediate1);
