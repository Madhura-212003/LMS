"""Bounded AST interpreter for introductory Python; never uses eval or exec.

This is a small teaching language, not a general Python sandbox. No imports,
attributes, functions, files, network, recursion or host object access.
"""
import ast
import operator


class RunnerError(ValueError):
    pass


def run(code, inputs=None):
    if len(code) > 12000:
        raise RunnerError('Code must be at most 12,000 characters.')
    env, output, budget = {}, [], [10000]
    values = iter(str(inputs or '').splitlines())
    binary = {ast.Add:operator.add, ast.Sub:operator.sub, ast.Mult:operator.mul, ast.Div:operator.truediv, ast.FloorDiv:operator.floordiv, ast.Mod:operator.mod}
    compare = {ast.Eq:operator.eq, ast.NotEq:operator.ne, ast.Lt:operator.lt, ast.LtE:operator.le, ast.Gt:operator.gt, ast.GtE:operator.ge}

    def check(value):
        if isinstance(value,(list,tuple)) and any(isinstance(x,(list,tuple,range)) for x in value):
            raise RunnerError('Nested collections are outside the teaching subset.')
        if isinstance(value,(str,list,tuple,range)) and len(value)>10000:
            raise RunnerError('Value exceeds the 10,000 item limit.')
        if isinstance(value,int) and value.bit_length()>256:
            raise RunnerError('Integer exceeds the teaching runner limit.')
        return value

    def tick():
        budget[0]-=1
        if budget[0]<0:
            raise RunnerError('Execution limit reached. Check your loops.')

    def expr(n):
        tick()
        if isinstance(n,ast.Constant) and type(n.value) in (int,float,str,bool,type(None)):
            return check(n.value)
        if isinstance(n,ast.Name):
            if n.id not in env: raise RunnerError('Unknown variable: '+n.id)
            return env[n.id]
        if isinstance(n,(ast.List,ast.Tuple)):
            return check([expr(x) for x in n.elts])
        if isinstance(n,ast.BinOp) and type(n.op) in binary:
            a,b=expr(n.left),expr(n.right)
            if isinstance(n.op,ast.Mult) and ((isinstance(a,(str,list)) and isinstance(b,int) and len(a)*abs(b)>10000) or (isinstance(b,(str,list)) and isinstance(a,int) and len(b)*abs(a)>10000)):
                raise RunnerError('Result exceeds the teaching runner limit.')
            return check(binary[type(n.op)](a,b))
        if isinstance(n,ast.UnaryOp):
            x=expr(n.operand)
            if isinstance(n.op,ast.USub):return check(-x)
            if isinstance(n.op,ast.Not):return not x
        if isinstance(n,ast.Compare):
            a=expr(n.left)
            for op,right in zip(n.ops,n.comparators):
                if type(op) not in compare:raise RunnerError('Unsupported comparison.')
                b=expr(right)
                if not compare[type(op)](a,b):return False
                a=b
            return True
        if isinstance(n,ast.BoolOp):
            return all(expr(v) for v in n.values) if isinstance(n.op,ast.And) else any(expr(v) for v in n.values)
        if isinstance(n,ast.Subscript):
            v,i=expr(n.value),expr(n.slice)
            if type(v) not in (list,str) or type(i) is not int:raise RunnerError('Only list/string integer indexing is supported.')
            return v[i]
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and not n.keywords:
            args=[expr(a) for a in n.args]
            name=n.func.id
            if name=='input':return next(values,'')
            if name=='print':
                line=' '.join(str(a) for a in args)
                if sum(len(x) for x in output)+len(line)>20000:raise RunnerError('Output limit reached.')
                output.append(line);return None
            if name=='range':
                if not 1<=len(args)<=3 or any(type(a) is not int or abs(a)>100000 for a in args):raise RunnerError('Range arguments must be bounded integers.')
                return check(range(*args))
            if name in ('int','float','str','len','sum','min','max','abs','round'):
                f={'int':int,'float':float,'str':str,'len':len,'sum':sum,'min':min,'max':max,'abs':abs,'round':round}[name]
                return check(f(*args))
        raise RunnerError('Unsupported syntax: '+type(n).__name__+'. Use variables, arithmetic, if, for/range, lists, input and print.')

    def block(nodes):
        for n in nodes:
            tick()
            if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):env[n.targets[0].id]=expr(n.value)
            elif isinstance(n,ast.AugAssign) and isinstance(n.target,ast.Name) and type(n.op) in binary:env[n.target.id]=check(binary[type(n.op)](env[n.target.id],expr(n.value)))
            elif isinstance(n,ast.Expr):expr(n.value)
            elif isinstance(n,ast.If):block(n.body if expr(n.test) else n.orelse)
            elif isinstance(n,ast.For) and isinstance(n.target,ast.Name):
                sequence=expr(n.iter)
                if type(sequence) not in (list,str,range):raise RunnerError('For loops require a list, string or range.')
                for v in sequence:env[n.target.id]=v;block(n.body)
            elif isinstance(n,ast.Pass):pass
            else:raise RunnerError('Unsupported statement: '+type(n).__name__)
    try:
        block(ast.parse(code).body)
        return '\n'.join(output)
    except RunnerError:raise
    except (SyntaxError,TypeError,ValueError,KeyError,IndexError,ZeroDivisionError,OverflowError,RecursionError) as e:
        raise RunnerError(str(e)[:200])
