fn f() {
    match x {
        ...
    }
    match y {
        ...,
        _ => 0,
    }
    match z {
        Some(v) => v,
        ...
    }
}
