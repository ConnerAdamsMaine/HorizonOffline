//! The offline/login player-name rule, shared by the game and local launchers.

/// StringUtil.isValidPlayerName, plus not empty (the login screen sends at least one character).
/// Printable ASCII includes punctuation; account-registration rules are narrower.
pub fn is_valid(name: &str) -> bool {
    (1..=16).contains(&name.len()) && name.chars().all(|c| c as u32 > 32 && (c as u32) < 127)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn offline_names_accept_printable_ascii_and_the_length_boundaries() {
        for name in [
            "Alex",
            "Alex_2",
            "A",
            "AB",
            "0123456789abcdef",
            "Alex-2",
            "!~",
        ] {
            assert!(is_valid(name), "{name:?}");
        }
        for byte in 33..=126 {
            assert!(is_valid(&char::from(byte).to_string()));
        }
    }

    #[test]
    fn offline_names_reject_empty_long_whitespace_control_and_unicode_names() {
        for name in [
            "",
            " ",
            " Alex",
            "Alex ",
            "two words",
            "0123456789abcdefg",
            "Alex\n",
            "A\tB",
            "A\0B",
            "A\u{7f}",
            "été",
            "玩家",
            "Alex\u{a0}",
        ] {
            assert!(!is_valid(name), "{name:?}");
        }
    }
}
